"""兜底清理：把测试账号名下的**所有**分组和短链删干净。

和 conftest 里 `cleanup_test_data` 的分工：

    cleanup_test_data（自动、每次跑完执行）
        只删「本次新增」—— 快照差集，精准，绝不误伤账号里的存量。

    clean_testdata.py（手动、按需执行）          ← 本脚本
        无差别清空 —— 兜底。

**什么时候需要它**：自动清理只删「本次新增」，所以它的基准（跑前快照）里含着
历史存量。一旦某轮跑到一半崩了、或清理自己失败了，那批残留就并入「存量」——
下次跑的快照里还有它们，**永远清不掉**。这时手动跑一次，把基准重置回干净状态。

⚠️ 正因为是「无差别清空」，它**只对专用测试账号安全** —— 账号里有别人的数据会一起删。

⚠️ 它和 conftest 的清理**共用同一份底层实现**（`fixtures/shortlink.py` 的
    `ShortlinkAdmin`）—— 列举和删除的动作只写一遍，这里只负责"删全部"这个策略。
    （原先两边各写了一份 `_all_groups` / `_all_links`，是重复代码。）

⚠️ 依赖框架（`Config` / `HttpClient` / 登录用例），和 `notify.py` 那种"不 import 框架"
   的 CI 胶水不是一类：它的活儿就是操作被测系统，和框架的关注点一致。
   前提是包已可编辑安装（`pip install -e .`），否则 `python scripts/xxx.py` 找不到包。

用法：
    ./.venv/Scripts/python.exe scripts/clean_testdata.py
"""

import sys
from pathlib import Path

# `python scripts/xxx.py` 时 sys.path[0] 是 scripts/，项目根不在里面 ——
# 手动补上，否则 import 不到 fixtures/（pytest_framework 那边靠 pip install -e . 解决）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fixtures.shortlink import ShortlinkAdmin  # noqa: E402
from pytest_framework.adapters.config import Config  # noqa: E402
from pytest_framework.adapters.execute_case import ExecuteCase  # noqa: E402
from pytest_framework.entities.context.context import Context  # noqa: E402
from pytest_framework.entities.model.case_model import CaseModel  # noqa: E402
from pytest_framework.infrastructure.http import HttpClient  # noqa: E402
from pytest_framework.infrastructure.logging.logger import init_logger  # noqa: E402
from pytest_framework.usecases.case_runner import CaseRunner  # noqa: E402

LOGIN_CASES = '/data/api_shortlink/login_post_account_login.yaml'


def main() -> None:
    init_logger()
    cfg = Config.load()
    context = Context(parent=cfg)
    client = HttpClient(cfg.get("shortlink.base_url"), timeout=cfg.get("http.timeout"))

    try:
        login_case = ExecuteCase.from_model(CaseModel(LOGIN_CASES))[0]
        CaseRunner(client, context).run(login_case)
        if not context.exists("token"):
            print("登录失败、拿不到 token —— 先确认被测服务开着，再跑一次。")
            return

        admin = ShortlinkAdmin(client, context.get("token"))
        snapshot = admin.snapshot()
        if snapshot is None:
            print("拿不到账号数据（服务不可用 / 业务码异常）—— 先确认被测服务开着。")
            return
        groups, links = snapshot

        # 先删短链、再删分组 —— 反过来的话分组没了，短链的 groupId 就悬空
        deleted_links = admin.delete_links(links)
        print(f"短链：账号下 {len(links)} 条，删除成功 {deleted_links} 条")

        deleted_groups = admin.delete_groups(groups)
        print(f"分组：账号下 {len(groups)} 个，删除成功 {deleted_groups} 个")

        print("清理完成。")
    finally:
        client.close()


if __name__ == "__main__":
    main()
