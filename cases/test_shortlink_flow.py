"""短链全生命周期 —— 「逃生舱」：流程里有**轮询等待**，yaml 场景表达不了。

按项目的约定：**流程线性的 → yaml 场景；有 如果/循环/等待 → 代码写**。
短链这条正好卡在"等待"上：

    `link/v1/add` 是**异步受理**的 —— 返回 `data=null`，**不给 code / mappingId**。
    要拿到标识符只能去 `link/v1/page` 查，而 MQ 消费要时间，于是**必须轮询**。

所以这一条流程用代码写，和 yaml 场景（分组那两条）共存。
"""

import logging
import time

import allure

from pytest_framework.entities.constants.logging import LogConfig
from pytest_framework.entities.context.context import Context
from pytest_framework.infrastructure.http import HttpClient

logger = logging.getLogger(f'{LogConfig.LOGGER_NAME}.cases.flow')

GROUP_ADD = '/link-server/api/group/v1/add'
GROUP_LIST = '/link-server/api/group/v1/list'
GROUP_DEL = '/link-server/api/group/v1/del'
DOMAIN_LIST = '/link-server/api/domain/v1/list'
LINK_ADD = '/link-server/api/link/v1/add'
LINK_PAGE = '/link-server/api/link/v1/page'
LINK_UPDATE = '/link-server/api/link/v1/update'
LINK_DEL = '/link-server/api/link/v1/del'

# 轮询等 MQ 消费：最多等 15 轮 × 2 秒 = 30 秒，够了
POLL_ROUNDS = 15
POLL_INTERVAL_SECONDS = 2
PAGE_SIZE = 100

# 一个固定的合法长链 —— 用例不验跳转，原样只是一个占位
ORIGINAL_URL = 'https://www.baidu.com'


def _create_group(client: HttpClient, headers: dict) -> str:
    """建一个组并返回它的 id（列表按 id 倒序，刚建的在第一个）。"""
    title = f'flow_group_{int(time.time())}'
    client.request("POST", GROUP_ADD, json={"title": title}, headers=headers)
    resp = client.request("GET", GROUP_LIST, headers=headers)
    return next(g["id"] for g in resp.json()["data"] if g["title"] == title)


def _official_domain(client: HttpClient, headers: dict) -> str:
    """官方域名的 id —— 建链要用。动态查而不是硬编码 "1"：换环境域名表会变。"""
    resp = client.request("GET", DOMAIN_LIST, headers=headers)
    return next(d["id"] for d in resp.json()["data"] if d["domainType"] == "OFFICIAL")


def _create_link(
    client: HttpClient, headers: dict, group_id: str, domain_id: str, title: str
) -> None:
    resp = client.request(
        "POST", LINK_ADD,
        json={
            "groupId": group_id,
            "title": title,
            "originalUrl": ORIGINAL_URL,
            "domainId": domain_id,
            "domainType": "OFFICIAL",
        },
        headers=headers,
    )
    assert resp.json()["code"] == 0, f"建链失败: {resp.json()}"


def _wait_for_link(
    client: HttpClient, headers: dict, group_id: str, title: str
) -> dict | None:
    """轮询 page，直到查到这条链 —— 建链是异步的，刚建完列表里还没有。

    等不到返回 None，由调用方断言（**不在这里静默返回空 dict**：那会把
    「MQ 没消费」伪装成「查到了但字段空」，后面全乱）。
    """
    for round_no in range(POLL_ROUNDS):
        resp = client.request(
            "POST", LINK_PAGE,
            json={"groupId": group_id, "page": 1, "size": PAGE_SIZE}, headers=headers,
        )
        current = (resp.json().get("data") or {}).get("current_data") or []
        for item in current:
            if item.get("title") == title:
                return item
        logger.info("第 %d 轮没等到短链进列表，%.0f 秒后重试", round_no + 1, POLL_INTERVAL_SECONDS)
        time.sleep(POLL_INTERVAL_SECONDS)
    return None


@allure.feature("短链平台")
class TestShortLinkFlow:
    """短链全生命周期（逃生舱）—— 为什么用代码而不是 yaml，见文件头。"""

    def test_link_lifecycle(
        self,
        shortlink_client: HttpClient,
        context: Context,
        shortlink_login,
        cleanup_test_data,
    ) -> None:
        """建组 → 建链 → 等 MQ → 改标题 → 删链 → 再删链。"""
        headers = {"Content-Type": "application/json", "token": context.get("token")}
        group_id = _create_group(shortlink_client, headers)
        try:
            domain_id = _official_domain(shortlink_client, headers)
            title = f'flow_link_{int(time.time())}'

            _create_link(shortlink_client, headers, group_id, domain_id, title)

            link = _wait_for_link(shortlink_client, headers, group_id, title)
            assert link is not None, (
                f"建链后 {POLL_ROUNDS * POLL_INTERVAL_SECONDS} 秒内没等到它进列表"
                "（MQ 没消费？还是建链其实失败了？）"
            )
            mapping_id, code = link["id"], link["code"]

            resp = shortlink_client.request(
                "POST", LINK_UPDATE,
                json={"mappingId": mapping_id, "code": code, "title": f"{title}_renamed"},
                headers=headers,
            )
            assert resp.json()["code"] == 0, f"改标题失败: {resp.json()}"

            resp = shortlink_client.request(
                "POST", LINK_DEL,
                json={"mappingId": mapping_id, "code": code}, headers=headers,
            )
            assert resp.json()["code"] == 0, f"删链失败: {resp.json()}"

            resp = shortlink_client.request(
                "POST", LINK_DEL,
                json={"mappingId": mapping_id, "code": code}, headers=headers,
            )
            assert resp.json()["code"] == 260404, f"重复删链该报「短链不存在」: {resp.json()}"
        finally:
            # 组自己收拾 —— 链在第 5 步已删；中途失败的话 cleanup_test_data 还会兜底
            shortlink_client.request(
                "DELETE", f"{GROUP_DEL}/{group_id}", headers=headers
            )

    def test_delete_group_keeps_link(
        self,
        shortlink_client: HttpClient,
        context: Context,
        shortlink_login,
        cleanup_test_data,
    ) -> None:
        """删组之后，组下**已建的短链**应该还在。

        原单接口用例「删除分组：删组不影响组下已建的短链」搬过来的 —— 它要一条真短链，
        而建链是异步的（得轮询等 MQ），所以进逃生舱而不是 yaml 场景。
        """
        headers = {"Content-Type": "application/json", "token": context.get("token")}
        group_id = _create_group(shortlink_client, headers)
        domain_id = _official_domain(shortlink_client, headers)
        title = f'flow_keep_{int(time.time())}'
        _create_link(shortlink_client, headers, group_id, domain_id, title)

        link = _wait_for_link(shortlink_client, headers, group_id, title)
        assert link is not None, (
            f"建链后 {POLL_ROUNDS * POLL_INTERVAL_SECONDS} 秒内没等到它进列表"
        )

        try:
            resp = shortlink_client.request(
                "DELETE", f"{GROUP_DEL}/{group_id}", headers=headers
            )
            assert resp.json()["code"] == 0, f"删组失败: {resp.json()}"

            # 组没了，但短链还在（全量查一遍，别按 groupId 查 —— 那个组已经不存在）
            resp = shortlink_client.request(
                "POST", LINK_PAGE,
                json={"page": 1, "size": PAGE_SIZE}, headers=headers,
            )
            codes = [
                it["code"]
                for it in (resp.json().get("data") or {}).get("current_data") or []
            ]
            assert link["code"] in codes, "删组把组下的短链也带走了（不该）"
        finally:
            # 组已经删了；把链也删掉（它是逻辑删，得走接口）
            shortlink_client.request(
                "POST", LINK_DEL,
                json={"mappingId": link["id"], "code": link["code"]}, headers=headers,
            )
