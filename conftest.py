import logging
import platform
import time
from pathlib import Path
from typing import Iterator

import pytest

from pytest_framework.adapters.config import Config
from pytest_framework.adapters.db_checker import DbChecker
from pytest_framework.adapters.execute_case import ExecuteCase
from pytest_framework.entities.constants.logging import LogConfig
from pytest_framework.entities.context.context import Context
from pytest_framework.entities.exception.errors import DataError
from pytest_framework.entities.model.case_model import CaseModel
from pytest_framework.infrastructure.db import MySqlExecutor
from pytest_framework.infrastructure.http import HttpClient
from pytest_framework.infrastructure.logging.logger import init_logger
from pytest_framework.infrastructure.logging.masking import configure_masking
from pytest_framework.infrastructure.path import _project_root
from pytest_framework.usecases.case_runner import CaseRunner

init_logger()

# conftest 自己的日志要冒泡到框架命名 logger 才进得了 logs/app.log。
# ⚠️ 用 `__name__` 会得到 "conftest"，冒泡到 root 就停，文件日志里一条都看不到。
logger = logging.getLogger(f'{LogConfig.LOGGER_NAME}.conftest')

# 短链平台的登录用例 —— 取【第一条】来拿 token，所以那条必须是成功登录且带 extract
SHORTLINK_LOGIN_CASES = '/data/api_shortlink/login_post_account_login.yaml'

# 短链平台的接口路径。用例走的是 yaml + `${}` 那套；这几个常量只服务 **conftest 自己**
# 的前置造数和事后清理 —— 它们不属于用例体系，所以不进 data/ 下的 yaml。
SHORTLINK_GROUP_ADD = '/link-server/api/group/v1/add'
SHORTLINK_GROUP_LIST = '/link-server/api/group/v1/list'
SHORTLINK_GROUP_DEL = '/link-server/api/group/v1/del'
SHORTLINK_DOMAIN_LIST = '/link-server/api/domain/v1/list'
SHORTLINK_LINK_PAGE = '/link-server/api/link/v1/page'
SHORTLINK_LINK_DEL = '/link-server/api/link/v1/del'

# 清理收网前多查几轮再定案：建链是**异步**的（等 MQ 消费才进 page 列表），
# 只查一次会把「刚建、还没消费完」的短链漏掉，残留到下一轮。
CLEANUP_ROUNDS = 2
CLEANUP_INTERVAL_SECONDS = 2
# 一页拉多少 —— 测试账号的数据量远小于这个数，一页足够
CLEANUP_PAGE_SIZE = 1000

# 公共前置分组的 title 前缀（带时间戳唯一化，见 shortlink_prepare）
PREPARE_GROUP_TITLE_PREFIX = 'at_prepare_'

# allure 的约定（插件注册的选项名 + 它认的文件名）—— 不是我们定的，所以是常量而非魔法值
ALLURE_DIR_OPTION = '--alluredir'
ENVIRONMENT_FILE = 'environment.properties'


@pytest.fixture(scope='session')
def config() -> Config:
    """整个会话共用的配置。

    **懒加载**：session 级 fixture 都是「第一次有人要才求值」—— 所以真正加载的时机
    是**第一条用例开始跑之前**，不是进程启动时。副作用是好的：只跑框架单测
    （`pytest tests/`）根本不会碰配置文件。

    加载完就定死：之后只读，跑的过程中不再变（所以要换环境只能重跑）。

    加载失败（文件没了 / 格式错）抛 ConfigError —— 配置坏了是硬错误，让它喊出来。

    顺手把**脱敏配置**喂给日志层：值特征随被测系统变（凭证在响应里长什么样，每个
    系统都不一样），归配置最合适。放在这里而不是模块导入时读，是为了让
    `pytest tests/` 跑框架单测时压根不碰配置文件。
    """
    cfg = Config.load()
    configure_masking(
        mode=cfg.get("masking.mode"),
        value_patterns=cfg.get("masking.value_patterns") or [],
    )
    return cfg


@pytest.fixture(scope='session')
def context(config: Config) -> Context:
    """整个会话共用一个变量池，**父级挂配置**。

    挂父级是为了让 ${...} 只有一个入口：`${token}` 查变量层（提取来的），
    `${shortlink.phone}` 落到配置层。用例作者不用区分两套语法。
    配置层是只读的 —— 用例 set 同名 key 只会写进自己层，覆盖不了配置。

    必须是 session 级：跨用例关联要共享，function / module 级每次重置就没法关联了。
    纯内存对象、没有资源要释放，所以不用 yield 收尾。

    ⚠️ 变量池是**进程内**的，开了 -n 分布式时每个 worker 各有一份，
    跨用例关联会失效 —— 有依赖的用例集不要开 -n。
    """
    return Context(parent=config)


# ---------- 被测系统：商用短链平台（Java / Spring Cloud） ----------
#
# 早期还有个 flaskServer 靶场，2026-10-12 已归档到 `archive/`（它是纯内存 mock、
# 没有数据库，「查库校验」那一步教不了）。现在框架只服务短链平台这一个系统。
@pytest.fixture(scope='session')
def shortlink_client(config: Config) -> Iterator[HttpClient]:
    """短链平台的 HTTP 客户端。

    session 级是为了**连接复用**（keep-alive）：整个会话建一次连接、跑完所有用例，
    比每条用例新建省得多。它不是为了图 cookie —— 本项目鉴权走 `token` 请求头。

    超时从配置读：不同环境网速差很多，写死在代码里换环境就得改代码。
    """
    http = HttpClient(
        config.get("shortlink.base_url"), timeout=config.get("http.timeout")
    )
    yield http
    http.close()


@pytest.fixture(scope='session')
def shortlink_login(shortlink_client: HttpClient, context: Context) -> None:
    """短链平台登录：整个会话只登一次，token 写进变量池。

    做法是**跑一条带 extract 的用例**（而不是裸调一次请求）—— 这样登录这条路径
    本身也在用例体系里，不会有一份"fixture 专用"的登录逻辑漂在外面。

    ⚠️ 短链平台的 token 放**请求头**（`token: <JWT>`），不是表单参数 ——
    所以用例里要写成 `headers: {token: "${token}"}`。
    """
    login_case = ExecuteCase.from_model(CaseModel(SHORTLINK_LOGIN_CASES))[0]
    CaseRunner(shortlink_client, context).run(login_case)


@pytest.fixture(scope='session')
def shortlink_prepare(shortlink_client: HttpClient, context: Context) -> Iterator[None]:
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
       这样也不依赖 fixture 之间的求值顺序（和 cleanup_test_data 谁先跑都行）。
    """
    token = context.get("token")
    headers = {"Content-Type": "application/json", "token": token}
    group_title = f"{PREPARE_GROUP_TITLE_PREFIX}{int(time.time())}"

    # 1. 建专用分组
    shortlink_client.request(
        "POST", SHORTLINK_GROUP_ADD, json={"title": group_title}, headers=headers,
    )

    # 2. 从列表里把它捞出来 —— add 接口**不返回 id**（data 恒 null），只能 list 查
    resp = shortlink_client.request("GET", SHORTLINK_GROUP_LIST, headers=headers)
    group_id = next(
        (g["id"] for g in resp.json().get("data") or [] if g.get("title") == group_title),
        None,
    )
    if group_id is None:
        # 前置造不出来是硬错误：早喊，别让下游几十条用例报莫名其妙的 ContextError
        raise DataError(f"前置分组没能建出来（title={group_title}），列表里查不到")
    context.set("g1_id", group_id)

    # 3. 官方域名的 id 入池（建链的 domainId/domainType）
    resp = shortlink_client.request("GET", SHORTLINK_DOMAIN_LIST, headers=headers)
    for domain in resp.json().get("data") or []:
        if domain.get("domainType") == "OFFICIAL":
            context.set("domain_id", domain["id"])
            context.set("domain_type", "OFFICIAL")
            break

    yield

    # 收尾：删掉自己建的组。失败只记 warning —— 清理是善后，不该影响测试结论
    try:
        shortlink_client.request(
            "DELETE", f"{SHORTLINK_GROUP_DEL}/{group_id}", headers=headers
        )
    except Exception as e:
        logger.warning("前置分组清理失败 id=%s：%s", group_id, e)


@pytest.fixture(scope='session')
def cleanup_test_data(
    shortlink_client: HttpClient, context: Context, shortlink_login
) -> Iterator[None]:
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
    headers = {"Content-Type": "application/json", "token": context.get("token")}

    def snapshot() -> tuple[set[str], dict[str, str]] | None:
        """当前账号下的数据：分组 id 集合 + 短链 {mappingId: code}。

        拿不到（token 失效 / 服务不可用 / 业务码非 0）返回 None，由调用方决定怎么
        处置 —— 不在这里抛：清理是 best-effort，不能让它自己变成新的失败源。
        """
        try:
            group_resp = shortlink_client.request(
                "GET", SHORTLINK_GROUP_LIST, headers=headers
            )
            link_resp = shortlink_client.request(
                "POST", SHORTLINK_LINK_PAGE,
                json={"page": 1, "size": CLEANUP_PAGE_SIZE}, headers=headers,
            )
        except Exception as e:
            logger.warning("清理：快照查询失败（%s）", e)
            return None

        group_body, link_body = group_resp.json(), link_resp.json()
        if group_body.get("code") != 0 or link_body.get("code") != 0:
            logger.warning(
                "清理：快照查询业务码异常（分组=%s 短链=%s）",
                group_body.get("code"), link_body.get("code"),
            )
            return None

        groups = {g["id"] for g in group_body.get("data") or []}
        page_data = link_body.get("data") or {}
        links = {item["id"]: item["code"] for item in page_data.get("current_data") or []}
        return groups, links

    before = snapshot()
    if before is None:
        # 连跑前快照都取不到，就没有基准可比 —— 宁可不清，也别把账号里的存量当"新增"删光
        logger.warning("清理跳过：跑前快照没取到，无法确定哪些是本次造的")
        yield
        return
    before_groups, before_links = before

    yield

    # 收网：多查几轮，把「刚建、MQ 还没消费完」的短链也收进来
    new_groups: set[str] = set()
    new_links: dict[str, str] = {}
    for round_no in range(CLEANUP_ROUNDS):
        current = snapshot()
        if current is None:
            break
        cur_groups, cur_links = current
        new_groups |= cur_groups - before_groups
        new_links.update({k: v for k, v in cur_links.items() if k not in before_links})
        if round_no < CLEANUP_ROUNDS - 1:
            time.sleep(CLEANUP_INTERVAL_SECONDS)

    # 先删短链、再删分组 —— 反过来的话分组没了，短链的 groupId 就悬空
    deleted_links = 0
    for mapping_id, code in new_links.items():
        try:
            resp = shortlink_client.request(
                "POST", SHORTLINK_LINK_DEL,
                json={"mappingId": mapping_id, "code": code}, headers=headers,
            )
            if resp.json().get("code") == 0:
                deleted_links += 1
        except Exception as e:
            logger.warning("清理：删短链失败 id=%s（%s）", mapping_id, e)

    deleted_groups = 0
    for group_id in new_groups:
        try:
            resp = shortlink_client.request(
                "DELETE", f"{SHORTLINK_GROUP_DEL}/{group_id}", headers=headers
            )
            if resp.json().get("code") == 0:
                deleted_groups += 1
        except Exception as e:
            logger.warning("清理：删分组失败 id=%s（%s）", group_id, e)

    logger.info(
        "清理完成：本次新增短链 %d 条 / 分组 %d 个，已删短链 %d / 分组 %d",
        len(new_links), len(new_groups), deleted_links, deleted_groups,
    )
    if deleted_links < len(new_links) or deleted_groups < len(new_groups):
        logger.warning("清理没删干净，可能有残留 —— 可跑 scripts/clean_testdata.py 兜底")


@pytest.fixture(scope='session')
def db_checker(config: Config) -> Iterator[DbChecker | None]:
    """查库校验器 —— 库校验那条路的入口。

    **没配 db 就返回 None**：纯接口用例照样跑，不会被数据库的可用性牵连。
    只有声明了 `db:` 断言的用例才会真去查、真报错。

    ⚠️ 光靠 fixture 的懒加载**挡不住**数据库不可用：消费方（用例函数）通常会把
    `db_checker` 写进签名，参数化展开出的**每条**用例都会拉它，所以它必然被求值。
    真正让"不查库的用例零成本"的是 `MySqlExecutor` 的**懒连接**（`__init__` 只记
    配置，第一条 `query()` 才连）—— 求值这个 fixture 只造一个空壳对象，一条 TCP
    都不会建；数据库真挂了，报错只会落在**声明了 `db:` 的用例**上。

    ⚠️ **当前没有用例在用它**（短链平台还没开只读库权限）。留着是因为
    `adapters/db_checker.py` / `ports/query.py` 那套能力还在，接上库就能用 ——
    归档的 `archive/flaskServer/data/api/db_check_cases.yaml` 有写法示例。
    """
    if not config.exists('db.host'):
        yield None
        return

    executor = MySqlExecutor(
        host=config.get('db.host'),
        port=config.get('db.port'),
        user=config.get('db.user'),
        password=config.get('db.password'),
        database=config.get('db.database'),
    )
    yield DbChecker(executor)
    executor.close()


@pytest.fixture(scope='session', autouse=True)
def _allure_environment(request: pytest.FixtureRequest) -> None:
    """把配置写进 allure 的 environment.properties（报告「环境」页）。

    没传 --alluredir 就直接不做 —— 不是每次跑用例都要出报告。
    ⚠️ 只写非敏感项：**密码绝不进报告**（报告是要发给别人看的）。

    ⚠️ `config` 依赖**故意不写在签名里**：fixture 的参数在函数体之前求值，而这是个
    autouse fixture —— 写进签名就等于**逼着每个会话都加载配置**，连 `pytest tests/`
    这种压根不出报告的场景也躲不掉（配置一坏，那批单测全 ERROR）。
    挪到函数体里 `getfixturevalue` 才是真惰性：没传 --alluredir 根本不碰配置。
    """
    allure_dir = request.config.getoption(ALLURE_DIR_OPTION, None)
    if not allure_dir:
        return

    config: Config = request.getfixturevalue('config')

    path = Path(allure_dir)
    if not path.is_absolute():
        # --alluredir 是相对 cwd 的，挂到项目根上再拼没有歧义
        path = _project_root() / path
    path.mkdir(parents=True, exist_ok=True)

    lines = [
        f'shortlink.base_url={config.get("shortlink.base_url")}',
        f'http.timeout={config.get("http.timeout")}',
        f'shortlink.phone={config.get("shortlink.phone")}',
        f'python={platform.python_version()}',
    ]
    (path / ENVIRONMENT_FILE).write_text('\n'.join(lines), encoding='utf-8')
