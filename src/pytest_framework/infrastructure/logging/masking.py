"""日志脱敏：日志落地前把敏感值打码。

为什么用自定义 Formatter，而不是 Filter / 调用点手打：

- 调用点手打：漏一处就泄漏，而且管不到 logger.exception 输出里的异常栈；
- logging.Filter：作用在 record 上、早于格式化，改结构化 args 得自己深拷贝，
  对栈文本也无能为力；
- 自定义 Formatter：所有 handler 挂同一个就全覆盖（包括将来的 allure handler），
  既能按 key 精确打码结构化 args，又能对最终文本做正则兜底。

**判定敏感有两条路，缺一不可**：

1. **按字段名**（`MaskConfig.SENSITIVE_KEYS`）—— 覆盖大多数情况：
   `password` / `token` / `phone`……
2. **按值的长相**（`value_patterns`）—— 有些系统把凭证塞在**普通字段名**里。
   短链平台就是：登录 token 装在 `data` 字段（key 叫 `data`，不是 `token`），
   光靠字段名匹配**一条都抓不到**。

⚠️ 值特征是**配置**不是常量：不同被测系统的凭证长相不同（flaskServer 的 token
   是裸随机串，短链平台的是 `dcloud-link` + JWT），框架不该认识任何具体系统。
   所以由 `conftest` 在加载配置后调 `configure_masking()` 喂进来。
"""

import copy
import logging
import re
from typing import Any

from pytest_framework.entities.constants.logging import MaskConfig, MaskMode

# 长 key 排前面，避免 access_token 被 token 抢先匹配掉
_KEYS = "|".join(sorted(MaskConfig.SENSITIVE_KEYS, key=len, reverse=True))

# 兜底用：匹配 passwd=xxx / 'token': 'xxx' 这类已渲染成文本的明文
_TEXT_PATTERN = re.compile(
    rf"(?i)({_KEYS})(['\"]?\s*[:=]\s*['\"]?)([^\s,'\"}}\]]+)"
)

# ---- 可配置项：由 configure_masking() 设置（见文件头的说明）----
_mode: str = MaskConfig.DEFAULT_MODE
_value_patterns: tuple[re.Pattern[str], ...] = ()


def configure_masking(
    mode: str | None = None,
    value_patterns: list[str] | None = None,
) -> None:
    """把「这一档 + 凭证长相」告诉脱敏层 —— 由 conftest 在配置加载后调用。

    **为什么不在模块导入时读配置**：`pytest tests/` 跑框架单测时不该碰生产配置，
    否则「框架单测零依赖」就成了空话（改一下 config 就能把单测带崩）。
    """
    global _mode, _value_patterns
    if mode:
        _mode = mode
    if value_patterns is not None:
        _value_patterns = tuple(re.compile(p) for p in value_patterns)


def _is_sensitive(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    return any(k in lowered for k in MaskConfig.SENSITIVE_KEYS)


def _looks_sensitive(value: Any) -> bool:
    """按「值的长相」判 —— 凭证被塞在普通字段名里时的兜底。

    **只认字符串**：数字、布尔不可能是凭证，也避免误伤（比如某个业务 id
    恰好是个长数字）。
    """
    if not isinstance(value, str):
        return False
    return any(p.search(value) for p in _value_patterns)


def mask(value: Any) -> Any:
    """递归给 dict / list 里的敏感值打码，返回新对象。

    一律产出副本：脱敏是「日志表现层」的事，绝不能碰到真正发出去的数据。
    命中时**保留 key 只换值** —— 删掉 key 反而丢掉「这里本来有值」的信息。
    """
    if _mode == MaskMode.OFF:
        return value

    if isinstance(value, dict):
        return {
            k: MaskConfig.MASK if _is_sensitive(k) or _looks_sensitive(v) else mask(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(mask(v) for v in value)
    # 裸字符串也要判一次 —— 比如 record.args 直接就是个 token
    if _looks_sensitive(value):
        return MaskConfig.MASK
    return value


def mask_text(text: str) -> str:
    """对已渲染的文本做正则兜底，覆盖 f-string 消息和异常栈里的明文。"""
    if _mode == MaskMode.OFF:
        return text
    return _TEXT_PATTERN.sub(rf"\1\2{MaskConfig.MASK}", text)


def install_masking() -> None:
    """装一个全局的 record 工厂，让**每一条**日志在创建时就打码。

    为什么不在 logger 上挂 Filter：
      logger 的 filter 只在 `Logger.handle()` 里对**直接记到该 logger**的消息执行，
      对从**子 logger 冒泡上来**的不执行。而框架里的日志全是
      `logging.getLogger(__name__)`（形如 pytest_framework.infrastructure.http），
      挂在 "framework" 上的 filter 根本轮不到 —— 这是个静默失效的坑。

    为什么不在 handler 上挂 Filter：
      pytest 失败时显示的「Captured log」用的是**它自己的 handler**，
      用例执行期间才动态挂到 root 上，我们够不着。

    所以从源头下手：record 一诞生就换成打码后的 args，之后所有出口
    （我们的控制台/文件、pytest 的捕获）拿到的都是同一份数据，不存在漏网。
    """
    original_factory = logging.getLogRecordFactory()

    def masking_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = original_factory(*args, **kwargs)
        if isinstance(record.args, dict):
            record.args = mask(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(mask(arg) for arg in record.args)
        return record

    logging.setLogRecordFactory(masking_factory)


class MaskingFormatter(logging.Formatter):
    """先按规则打码结构化 args，再对最终文本兜底。

    和全局 record 工厂是双保险：工厂管所有出口，Formatter 额外负责
    **最终文本和异常栈**的正则兜底（这部分工厂拿不到）。
    """

    def format(self, record: logging.LogRecord) -> str:
        # 只在副本上动手：原 record 可能还要被别的 handler 用
        copy_record = copy.copy(record)
        if isinstance(copy_record.args, dict):
            copy_record.args = mask(copy_record.args)
        elif isinstance(copy_record.args, tuple):
            copy_record.args = tuple(mask(arg) for arg in copy_record.args)

        return mask_text(super().format(copy_record))
