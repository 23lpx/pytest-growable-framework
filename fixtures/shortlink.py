"""短链平台的访问层 + 测试数据治理 —— 纯逻辑，不依赖 pytest。

**这个模块是什么**：所有「怎么和短链平台打交道」的知识收在这一层 —— 接口路径、
请求体形状、token 放哪、建组为什么不返回 id、建链为什么是异步的。**用例和 fixture
都复用它，不各自拼一遍。**

**为什么单独一个模块**：这些代码原先分散在两处 —— 一部分长在 `conftest.py` 里
（它当时 363 行），一部分在 `cases/test_shortlink_flow.py` 里又写了一套：同一批接口
路径定义了两遍，建组、查官方域名这些动作也重复。而 `conftest.py` 是 Composition
Root，职责是「组装 + 声明」，更不该承载这些。

判据很直接：**这里的东西一件都不需要 pytest 就能跑。**
`scripts/clean_testdata.py` 也在复用同一个 `ShortlinkAdmin`。

三块：

  · `ShortlinkAdmin`           访问层：列举 / 创建 / 删除（只认 `Sender` 端口）
  · `prepare_shortlink_data`   造只读公共前置（generator，yield 之后收尾删自己的）
  · `cleanup_shortlink_data`   快照差集清理（generator，yield 之后删本次新增的）
"""

import logging
import time
from typing import Iterator

from pytest_framework.entities.constants.logging import LogConfig
from pytest_framework.entities.context.context import Context
from pytest_framework.entities.contracts import ResponseLike
from pytest_framework.entities.exception.errors import DataError
from pytest_framework.ports.sender import Sender

# ⚠️ 必须挂在框架命名空间下才能进 logs/app.log —— 各模块的 handler 挂在
#    `pytest_framework` 这个 logger 上。用裸 `__name__` 会得到 "fixtures.shortlink"，
#    冒泡到 root 就停，日志静悄悄全丢（同坑 ⑯）。
logger = logging.getLogger(f'{LogConfig.LOGGER_NAME}.fixtures.shortlink')

# ---------- 短链平台的接口路径 ----------
GROUP_ADD = '/link-server/api/group/v1/add'
GROUP_LIST = '/link-server/api/group/v1/list'
GROUP_DEL = '/link-server/api/group/v1/del'
DOMAIN_LIST = '/link-server/api/domain/v1/list'
LINK_ADD = '/link-server/api/link/v1/add'
LINK_PAGE = '/link-server/api/link/v1/page'
LINK_UPDATE = '/link-server/api/link/v1/update'
LINK_DEL = '/link-server/api/link/v1/del'

JSON_HEADERS = {'Content-Type': 'application/json'}

DOMAIN_TYPE_OFFICIAL = 'OFFICIAL'

# 一页拉多少 —— 测试账号的数据量远小于这个数，一页足够
PAGE_SIZE = 1000

# 清理收网前多查几轮再定案：建链是**异步**的（等 MQ 消费才进 page 列表），
# 只查一次会把「刚建、还没消费完」的短链漏掉，残留到下一轮。
CLEANUP_ROUNDS = 2
CLEANUP_INTERVAL_SECONDS = 2

# 公共前置分组的 title 前缀（带时间戳唯一化，见 prepare_shortlink_data）
PREPARE_GROUP_TITLE_PREFIX = 'at_prepare_'


class ShortlinkAdmin:
    """按账号操作短链平台：列举 / 创建 / 删除。

    只认 `ports.Sender`（能把请求发出去），**不认识 `HttpClient`** —— 和框架内部
    同一个规矩：依赖端口，不依赖实现。好处是将来能注入假的 Sender 做单测。

    定位：**「怎么调这个平台」的知识全在这儿**。调用方只负责「调完怎么判」——
    需要断言就拿返回的响应自己断（方法返回 `ResponseLike`，不替调用方判成败）。
    例外是清理类的批量方法：返回成功条数、失败只记 warning（清理是 best-effort）。
    """

    def __init__(self, client: Sender, token: str) -> None:
        self._client = client
        self._headers = {**JSON_HEADERS, 'token': token}

    # ---------- 分组 ----------

    def create_group(self, title: str) -> str:
        """建一个分组，返回它的 id。

        ⚠️ add 接口**不返回 id**（data 恒 null），只能建完再去 list 里按 title 捞 ——
        所以 **title 必须唯一**（调用方带时间戳）。
        """
        self._client.request('POST', GROUP_ADD, json={'title': title}, headers=self._headers)
        resp = self._client.request('GET', GROUP_LIST, headers=self._headers)
        group_id = next(
            (g['id'] for g in resp.json().get('data') or [] if g.get('title') == title),
            None,
        )
        if group_id is None:
            raise DataError(f'分组没能建出来（title={title}），列表里查不到')
        return group_id

    def delete_groups(self, groups: set[str]) -> int:
        """逐个删分组，返回**删除成功数**。单条失败只记 warning、继续下一个。"""
        deleted = 0
        for group_id in groups:
            try:
                resp = self._client.request(
                    'DELETE', f'{GROUP_DEL}/{group_id}', headers=self._headers
                )
                if resp.json().get('code') == 0:
                    deleted += 1
            except Exception as e:
                logger.warning('删分组失败 id=%s（%s）', group_id, e)
        return deleted

    # ---------- 域名 ----------

    def official_domain_id(self) -> str:
        """官方域名的 id —— 建链要用。**动态查而不是硬编码 "1"**：换环境域名表会变。"""
        resp = self._client.request('GET', DOMAIN_LIST, headers=self._headers)
        domain_id = next(
            (
                d['id']
                for d in resp.json().get('data') or []
                if d.get('domainType') == DOMAIN_TYPE_OFFICIAL
            ),
            None,
        )
        if domain_id is None:
            raise DataError('域名表里没有 OFFICIAL 类型的域名，建链的前置不成立')
        return domain_id

    # ---------- 短链 ----------

    def page_links(self, group_id: str | None = None, size: int = PAGE_SIZE) -> list[dict]:
        """翻一页短链，返回当前页的条目。传 groupId 就只看那个组下的。"""
        payload: dict = {'page': 1, 'size': size}
        if group_id:
            payload['groupId'] = group_id
        _, items = self._link_page_raw(payload)
        return items

    def create_link(
        self, group_id: str, domain_id: str, title: str, original_url: str
    ) -> ResponseLike:
        """建链。⚠️ **异步受理**：返回 `data=null`，**不给 code / mappingId** ——
        要拿标识符只能去 `page_links` 里轮询（等 MQ 消费）。"""
        return self._client.request(
            'POST', LINK_ADD,
            json={
                'groupId': group_id,
                'title': title,
                'originalUrl': original_url,
                'domainId': domain_id,
                'domainType': DOMAIN_TYPE_OFFICIAL,
            },
            headers=self._headers,
        )

    def update_link_title(self, mapping_id: str, code: str, title: str) -> ResponseLike:
        return self._client.request(
            'POST', LINK_UPDATE,
            json={'mappingId': mapping_id, 'code': code, 'title': title},
            headers=self._headers,
        )

    def delete_link(self, mapping_id: str, code: str) -> ResponseLike:
        """删一条短链。⚠️ 删链要 `mappingId` **和** `code` 两个字段。"""
        return self._client.request(
            'POST', LINK_DEL,
            json={'mappingId': mapping_id, 'code': code},
            headers=self._headers,
        )

    def delete_links(self, links: dict[str, str]) -> int:
        """逐个删短链（入参是 `{mappingId: code}`），返回**删除成功数**。

        和 `delete_link` 的分工：这个是**清理用**的批量版，失败只记 warning、
        不往外抛（清理是 best-effort，网络抖动不该让测试结论变色）。
        """
        deleted = 0
        for mapping_id, code in links.items():
            try:
                if self.delete_link(mapping_id, code).json().get('code') == 0:
                    deleted += 1
            except Exception as e:
                logger.warning('删短链失败 id=%s（%s）', mapping_id, e)
        return deleted

    # ---------- 快照 ----------

    def snapshot(self) -> tuple[set[str], dict[str, str]] | None:
        """当前账号下的数据：分组 id 集合 + 短链 {mappingId: code}。

        拿不到（token 失效 / 服务不可用 / 业务码非 0）返回 None，由调用方决定怎么
        处置 —— 不在这里抛：清理是 best-effort，不能让它自己变成新的失败源。
        """
        try:
            group_resp = self._client.request('GET', GROUP_LIST, headers=self._headers)
            link_code, items = self._link_page_raw({'page': 1, 'size': PAGE_SIZE})
        except Exception as e:
            logger.warning('快照查询失败（%s）', e)
            return None

        group_body = group_resp.json()
        if group_body.get('code') != 0 or link_code != 0:
            logger.warning(
                '快照查询业务码异常（分组=%s 短链=%s）',
                group_body.get('code'), link_code,
            )
            return None

        groups = {g['id'] for g in group_body.get('data') or []}
        links = {item['id']: item['code'] for item in items}
        return groups, links

    # ---------- 内部 ----------

    def _link_page_raw(self, payload: dict) -> tuple[int, list[dict]]:
        """翻页短链，返回 `(业务码, 当前页条目)`。

        单拎出来是因为两处都要它、但要的东西不同：`snapshot` 要**业务码**做安全检查，
        `page_links` 只要**数据**。
        """
        resp = self._client.request('POST', LINK_PAGE, json=payload, headers=self._headers)
        body = resp.json()
        data = body.get('data') or {}
        return body.get('code'), data.get('current_data') or []


def prepare_shortlink_data(client: Sender, context: Context) -> Iterator[None]:
    """造短链平台用例要用的**只读**公共前置，写进变量池。

    **为什么要有它**：分组详情/更新的路径参数、建链的 groupId 都要一个真实分组。
    这些是**测试自己该准备的数据** —— 不该指望"环境里碰巧有"（碰巧有会过，
    清一次库就全挂，是最难查的那种不稳定）。

    造两样东西：
      · 一个专用分组    → `${g1_id}`（分组详情/更新的路径参数、建链的 groupId）
      · 官方域名        → `${domain_id}` / `${domain_type}`（建链要用）

    ⚠️ **契约：这是只读前置**。任何用例都不许删它、改它 —— 需要删改分组的一律走
       场景（自己造一次性数据）。这是「单接口互不依赖」的落地方式：依赖一个
       **稳定的只读前置**不算互相依赖，依赖一个**会被别人改掉的状态**才是。

    ⚠️ title 带时间戳**唯一化**，不用固定的 "g1"：分组是物理删除，万一上一轮的
       残留没清干净，固定 title 会撞 23001，把「正常建组」逼挂。

    ⚠️ 用 yield 收尾**删掉自己建的组**：自己的资源自己回收，不指望别人 ——
       这样也不依赖 fixture 之间的求值顺序（和 cleanup 谁先跑都行）。
    """
    admin = ShortlinkAdmin(client, context.get('token'))

    group_id = admin.create_group(f'{PREPARE_GROUP_TITLE_PREFIX}{int(time.time())}')
    context.set('g1_id', group_id)

    context.set('domain_id', admin.official_domain_id())
    context.set('domain_type', DOMAIN_TYPE_OFFICIAL)

    yield

    # 收尾：删掉自己建的组。失败只记 warning —— 清理是善后，不该影响测试结论
    if admin.delete_groups({group_id}) == 0:
        logger.warning('前置分组清理失败 id=%s', group_id)


def cleanup_shortlink_data(client: Sender, context: Context) -> Iterator[None]:
    """会话结束，把**本次跑造出来的**数据清掉 —— 快照差集。

    **为什么是快照差集，不是按 title 前缀扫**：有一批用例的 title **本身就是测试点**
    （255 个字符、SQL 注入串、前导空格…），加不了任何前缀；按 id 做快照差集就完全
    不看 title 长什么样，这批也能清干净。

    **为什么不做 autouse**：根 conftest 的 autouse fixture 会连 `tests/` 里那批框架
    单测一起触发 —— 它们的目标是「零外部依赖」，被拉去连被测服务就废了（同坑 ⑭）。
    所以**显式挂**在用例文件上。

    ⚠️ **前提：测试账号是专用的**。差集假设「跑前没有、跑后有了」＝ 本次造的；
       若同时有别人往这个账号写数据，会被误当成本次造的一起删掉。

    ⚠️ **清理失败不改测试结论**（只记 warning）：清理是善后，网络抖动、服务抽风都会
       让它失败，那不是「测试失败」。真留了残留，用 `scripts/clean_testdata.py` 兜底。
    """
    admin = ShortlinkAdmin(client, context.get('token'))

    before = admin.snapshot()
    if before is None:
        # 连跑前快照都取不到，就没有基准可比 —— 宁可不清，也别把账号里的存量当"新增"删光
        logger.warning('清理跳过：跑前快照没取到，无法确定哪些是本次造的')
        yield
        return
    before_groups, before_links = before

    yield

    # 收网：多查几轮，把「刚建、MQ 还没消费完」的短链也收进来
    new_groups: set[str] = set()
    new_links: dict[str, str] = {}
    for round_no in range(CLEANUP_ROUNDS):
        current = admin.snapshot()
        if current is None:
            break
        cur_groups, cur_links = current
        new_groups |= cur_groups - before_groups
        new_links.update({k: v for k, v in cur_links.items() if k not in before_links})
        if round_no < CLEANUP_ROUNDS - 1:
            time.sleep(CLEANUP_INTERVAL_SECONDS)

    # 先删短链、再删分组 —— 反过来的话分组没了，短链的 groupId 就悬空
    deleted_links = admin.delete_links(new_links)
    deleted_groups = admin.delete_groups(new_groups)

    logger.info(
        '清理完成：本次新增短链 %d 条 / 分组 %d 个，已删短链 %d / 分组 %d',
        len(new_links), len(new_groups), deleted_links, deleted_groups,
    )
    if deleted_links < len(new_links) or deleted_groups < len(new_groups):
        logger.warning('清理没删干净，可能有残留 —— 可跑 scripts/clean_testdata.py 兜底')
