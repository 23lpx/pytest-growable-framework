"""CI 跑完，把测试结果发出去 —— 钉钉 / 邮件共用这一个入口。

**独立脚本，不 import 框架**：它的活儿只有一件 —— 读 pytest 的 junit.xml、
拼一条消息、往各渠道发。所以它不该知道 CaseRunner / Context 这些概念，
将来换个项目也能直接拿去用。

结构是「解析 / 渲染 / 分发」三段：

    junit.xml ─▶ parse_junit ─▶ TestSummary ─▶ render ─▶ send_*
      (数据)       (解析)        (结构化)      (渲染)    (分发)

加一个渠道 = 加一个 `send_xxx` + 在 `_send_all` 里挂一行，**解析和渲染一个字不用动**。

⚠️ 通知是**尽力而为**：某个渠道发失败只打日志、不拖累另一个，也不改 CI 的成败
（测试失败本身已经由 CI 判了）。这里 `except Exception` 是有意放宽的 ——
SMTP 和 requests 能抛的异常种类太多，逐个列既列不全也没意义。
"""

import argparse
import base64
import hashlib
import hmac
import os
import smtplib
import sys
import time
import urllib.parse
from collections.abc import Iterable
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from pathlib import Path
from xml.etree import ElementTree

import requests

# ── 环境变量名（CI 里从 GitHub Secrets 注入，本地不配就跳过）──
ENV_DINGTALK_WEBHOOK = "DINGTALK_WEBHOOK"
ENV_DINGTALK_SECRET = "DINGTALK_SECRET"
ENV_SMTP_HOST = "SMTP_HOST"
ENV_SMTP_PORT = "SMTP_PORT"
ENV_SMTP_USER = "SMTP_USER"
ENV_SMTP_PASSWORD = "SMTP_PASSWORD"
ENV_MAIL_TO = "MAIL_TO"
ENV_MAIL_FROM = "MAIL_FROM"

# 钉钉自定义机器人的消息类型。文本最省事，且「加签」方式对文本不限关键词。
DINGTALK_MSGTYPE_TEXT = "text"

# SMTP 默认端口：465 是 SSL。国内主流邮箱都支持，比 587 的 STARTTLS 少一次握手。
DEFAULT_SMTP_PORT = 465

# 消息里最多列几条失败用例 —— 失败上百条时不能把消息撑爆。
MAX_LISTED_FAILURES = 10

# 网络超时：通知是收尾动作，宁可失败也不能卡住 CI。
REQUEST_TIMEOUT = 10


@dataclass
class TestSummary:
    """一次测试跑完的结构化结果 —— 渠道渲染的就是它，不是原始 XML。

    字段直接从 junit 的 testsuite 属性取，不做二次加工：junit 已经
    把「多少条、错几条」算好了，自己再统计一遍只会引入分歧。
    """

    total: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    duration: float = 0.0
    failed_cases: list[str] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return self.total - self.failures - self.errors - self.skipped

    @property
    def ok(self) -> bool:
        return self.failures == 0 and self.errors == 0


def parse_junit(path: Path) -> TestSummary:
    """读 pytest `--junitxml` 生成的标准结果。

    pytest 写的根节点是 `<testsuites>`，底下挂 N 个 `<testsuite>`；
    也兼容直接是 `<testsuite>` 的情况（别的工具生成的格式）。
    """
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root)

    summary = TestSummary()
    for suite in suites:
        summary.total += int(suite.get("tests", 0))
        summary.failures += int(suite.get("failures", 0))
        summary.errors += int(suite.get("errors", 0))
        summary.skipped += int(suite.get("skipped", 0))
        summary.duration += float(suite.get("time", 0))
        summary.failed_cases.extend(_failed_cases(suite))
    return summary


def _failed_cases(suite: ElementTree.Element) -> Iterable[str]:
    """挑出失败 / 报错的用例名。

    junit 判定靠子节点：挂 `<failure>` 是断言失败，挂 `<error>` 是出错，
    两者都算「没通过」—— 通知里不细分，反正都得去看。
    """
    for case in suite.iter("testcase"):
        if case.find("failure") is not None or case.find("error") is not None:
            yield f"{case.get('classname', '')}::{case.get('name', '')}"


def render(summary: TestSummary, title: str) -> str:
    """把结果拼成人读的文本 —— 钉钉和邮件用的是同一份，不重复写。"""
    status = "✅ 通过" if summary.ok else "❌ 失败"
    lines = [
        f"{title}：{status}",
        f"总数 {summary.total}｜通过 {summary.passed}｜"
        f"失败 {summary.failures + summary.errors}｜跳过 {summary.skipped}",
        f"耗时 {summary.duration:.2f}s",
    ]
    if summary.failed_cases:
        lines.append("失败用例：")
        lines.extend(f"  - {name}" for name in summary.failed_cases[:MAX_LISTED_FAILURES])
        rest = len(summary.failed_cases) - MAX_LISTED_FAILURES
        if rest > 0:
            lines.append(f"  ...（还有 {rest} 条）")
    return "\n".join(lines)


def send_dingtalk(text: str) -> None:
    """发钉钉机器人。没配 webhook 就跳过 —— 本地跑不该因为这个报错。"""
    webhook = os.getenv(ENV_DINGTALK_WEBHOOK, "")
    if not webhook:
        print("[钉钉] 没配 DINGTALK_WEBHOOK，跳过")
        return

    resp = requests.post(
        _signed_webhook(webhook, os.getenv(ENV_DINGTALK_SECRET, "")),
        json={"msgtype": DINGTALK_MSGTYPE_TEXT, "text": {"content": text}},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    print("[钉钉] 已发送")


def _signed_webhook(webhook: str, secret: str) -> str:
    """按钉钉的「加签」规则补上 timestamp + sign。

    这是钉钉对自定义机器人的安全要求（防伪造），不是我们定的规矩。
    没配 secret 就原样返回 —— 那种情况机器人走的是「关键词」校验。
    """
    if not secret:
        return webhook

    timestamp = str(round(time.time() * 1000))
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}\n{secret}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(digest).decode("utf-8"))
    return f"{webhook}&timestamp={timestamp}&sign={sign}"


def send_email(text: str, title: str) -> None:
    """发邮件。没配 SMTP_HOST 就跳过。"""
    host = os.getenv(ENV_SMTP_HOST, "")
    if not host:
        print("[邮件] 没配 SMTP_HOST，跳过")
        return

    user = os.getenv(ENV_SMTP_USER, "")
    mail_to = os.getenv(ENV_MAIL_TO, "")
    mail_from = os.getenv(ENV_MAIL_FROM, "") or user

    message = MIMEText(text, "plain", "utf-8")
    message["Subject"] = title
    message["From"] = mail_from
    message["To"] = mail_to

    with smtplib.SMTP_SSL(
        host, int(os.getenv(ENV_SMTP_PORT, DEFAULT_SMTP_PORT)), timeout=REQUEST_TIMEOUT
    ) as smtp:
        smtp.login(user, os.getenv(ENV_SMTP_PASSWORD, ""))
        # 收件人允许逗号分隔的多个，逐个 strip —— 配置里手写的空格很常见
        smtp.sendmail(mail_from, [a.strip() for a in mail_to.split(",")], message.as_string())
    print("[邮件] 已发送")


def _send_all(text: str, *, title: str) -> None:
    """逐个渠道发，一个失败不影响另一个。

    `except Exception` 在这里是**有意的**：通知属于收尾动作，不能因为它
    挂了就把 CI 判成失败 —— 真正决定 CI 成败的是测试本身。
    """
    channels = (
        ("钉钉", lambda: send_dingtalk(text)),
        ("邮件", lambda: send_email(text, title)),
    )
    for name, send in channels:
        try:
            send()
        except Exception as e:
            print(f"[{name}] 发送失败：{e}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="把 pytest 结果发到钉钉 / 邮件")
    parser.add_argument("junit", type=Path, help="pytest --junitxml 生成的报告")
    parser.add_argument("--title", default="接口自动化框架", help="消息抬头")
    args = parser.parse_args()

    if not args.junit.exists():
        # 连结果文件都没有，说明测试压根没跑起来 —— 没什么可通知的。
        # 退出码给 0：这不是通知环节的错，别让它再压上一层假失败。
        print(f"找不到 {args.junit}，跳过通知", file=sys.stderr)
        sys.exit(0)

    summary = parse_junit(args.junit)
    text = render(summary, title=args.title)
    print(text)  # CI 日志里也留一份，出问题时不用翻别处

    _send_all(text, title=args.title)


if __name__ == "__main__":
    main()
