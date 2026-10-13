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

⚠️ 依赖框架（`Config` / `HttpClient` / 登录用例），和 `notify.py` 那种"不 import 框架"
   的 CI 胶水不是一类：它的活儿就是操作被测系统，和框架的关注点一致。
   前提是包已可编辑安装（`pip install -e .`），否则 `python scripts/xxx.py` 找不到包。

用法：
    ./.venv/Scripts/python.exe scripts/clean_testdata.py
"""

from pytest_framework.adapters.config import Config
from pytest_framework.adapters.execute_case import ExecuteCase
from pytest_framework.entities.context.context import Context
from pytest_framework.entities.model.case_model import CaseModel
from pytest_framework.infrastructure.http import HttpClient
from pytest_framework.infrastructure.logging.logger import init_logger
from pytest_framework.usecases.case_runner import CaseRunner

LOGIN_CASES = '/data/api_shortlink/login_post_account_login.yaml'

GROUP_LIST = '/link-server/api/group/v1/list'
GROUP_DEL = '/link-server/api/group/v1/del'
LINK_PAGE = '/link-server/api/link/v1/page'
LINK_DEL = '/link-server/api/link/v1/del'

# 一页拉多少 —— 测试账号的数据量远小于这个数，一页足够
PAGE_SIZE = 1000


def _all_groups(client: HttpClient, headers: dict) -> set[str]:
    """账号下所有分组的 id。"""
    resp = client.request("GET", GROUP_LIST, headers=headers)
    return {g["id"] for g in resp.json().get("data") or []}


def _all_links(client: HttpClient, headers: dict) -> dict[str, str]:
    """账号下所有短链的 {mappingId: code} —— 删链两个字段都要。"""
    resp = client.request(
        "POST", LINK_PAGE, json={"page": 1, "size": PAGE_SIZE}, headers=headers
    )
    data = resp.json().get("data") or {}
    return {item["id"]: item["code"] for item in data.get("current_data") or []}


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
        headers = {"Content-Type": "application/json", "token": context.get("token")}

        # 先删短链、再删分组 —— 反过来的话分组没了，短链的 groupId 就悬空
        links = _all_links(client, headers)
        deleted_links = 0
        for mapping_id, code in links.items():
            resp = client.request(
                "POST", LINK_DEL,
                json={"mappingId": mapping_id, "code": code}, headers=headers,
            )
            if resp.json().get("code") == 0:
                deleted_links += 1
        print(f"短链：账号下 {len(links)} 条，删除成功 {deleted_links} 条")

        groups = _all_groups(client, headers)
        deleted_groups = 0
        for group_id in groups:
            resp = client.request(
                "DELETE", f"{GROUP_DEL}/{group_id}", headers=headers
            )
            if resp.json().get("code") == 0:
                deleted_groups += 1
        print(f"分组：账号下 {len(groups)} 个，删除成功 {deleted_groups} 个")

        print("清理完成。")
    finally:
        client.close()


if __name__ == "__main__":
    main()
