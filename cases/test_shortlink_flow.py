"""短链全生命周期 —— 「逃生舱」：流程里有**轮询等待**，yaml 场景表达不了。

按项目的约定：**流程线性的 → yaml 场景；有 如果/循环/等待 → 代码写**。
短链这条正好卡在"等待"上：

    `link/v1/add` 是**异步受理**的 —— 返回 `data=null`，**不给 code / mappingId**。
    要拿到标识符只能去 `link/v1/page` 查，而 MQ 消费要时间，于是**必须轮询**。

所以这一条流程用代码写，和 yaml 场景（分组那两条）共存。

**接口路径、建组、查域名这些都不在这儿** —— 它们归 `fixtures/shortlink.py` 的
`ShortlinkAdmin`（和 conftest 的前置/清理共用一份）。这个文件只留**用例自己的事**：
流程控制（轮询）和断言。
"""

import logging
import time

import allure

from fixtures.shortlink import ShortlinkAdmin
from pytest_framework.entities.constants.logging import LogConfig
from pytest_framework.entities.context.context import Context
from pytest_framework.infrastructure.http import HttpClient

logger = logging.getLogger(f'{LogConfig.LOGGER_NAME}.cases.flow')

# 轮询等 MQ 消费：最多等 15 轮 × 2 秒 = 30 秒，够了
POLL_ROUNDS = 15
POLL_INTERVAL_SECONDS = 2

# 一个固定的合法长链 —— 用例不验跳转，原样只是一个占位
ORIGINAL_URL = 'https://www.baidu.com'


def _wait_for_link(admin: ShortlinkAdmin, group_id: str, title: str) -> dict | None:
    """轮询 page，直到查到这条链 —— 建链是异步的，刚建完列表里还没有。

    等不到返回 None，由调用方断言（**不在这里静默返回空 dict**：那会把
    「MQ 没消费」伪装成「查到了但字段空」，后面全乱）。
    """
    for round_no in range(POLL_ROUNDS):
        for item in admin.page_links(group_id=group_id):
            if item.get('title') == title:
                return item
        logger.info(
            '第 %d 轮没等到短链进列表，%.0f 秒后重试', round_no + 1, POLL_INTERVAL_SECONDS
        )
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
        admin = ShortlinkAdmin(shortlink_client, context.get('token'))
        group_id = admin.create_group(f'flow_group_{int(time.time())}')
        try:
            domain_id = admin.official_domain_id()
            title = f'flow_link_{int(time.time())}'

            resp = admin.create_link(group_id, domain_id, title, ORIGINAL_URL)
            assert resp.json()['code'] == 0, f'建链失败: {resp.json()}'

            link = _wait_for_link(admin, group_id, title)
            assert link is not None, (
                f'建链后 {POLL_ROUNDS * POLL_INTERVAL_SECONDS} 秒内没等到它进列表'
                '（MQ 没消费？还是建链其实失败了？）'
            )
            mapping_id, code = link['id'], link['code']

            resp = admin.update_link_title(mapping_id, code, f'{title}_renamed')
            assert resp.json()['code'] == 0, f'改标题失败: {resp.json()}'

            resp = admin.delete_link(mapping_id, code)
            assert resp.json()['code'] == 0, f'删链失败: {resp.json()}'

            resp = admin.delete_link(mapping_id, code)
            assert resp.json()['code'] == 260404, f'重复删链该报「短链不存在」: {resp.json()}'
        finally:
            # 组自己收拾 —— 链在第 5 步已删；中途失败的话 cleanup_test_data 还会兜底
            admin.delete_groups({group_id})

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
        admin = ShortlinkAdmin(shortlink_client, context.get('token'))
        group_id = admin.create_group(f'flow_group_{int(time.time())}')
        domain_id = admin.official_domain_id()
        title = f'flow_keep_{int(time.time())}'

        resp = admin.create_link(group_id, domain_id, title, ORIGINAL_URL)
        assert resp.json()['code'] == 0, f'建链失败: {resp.json()}'

        link = _wait_for_link(admin, group_id, title)
        assert link is not None, (
            f'建链后 {POLL_ROUNDS * POLL_INTERVAL_SECONDS} 秒内没等到它进列表'
        )

        try:
            resp = admin.delete_groups({group_id})
            assert resp == 1, '删组失败'

            # 组没了，但短链还在（全量查一遍，别按 groupId 查 —— 那个组已经不存在）
            codes = [item['code'] for item in admin.page_links()]
            assert link['code'] in codes, '删组把组下的短链也带走了（不该）'
        finally:
            # 组已经删了；把链也删掉（它是逻辑删，得走接口）
            admin.delete_link(link['id'], link['code'])
