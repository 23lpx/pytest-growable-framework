"""Composition Root（组装根）—— 只做两件事：**组装** + **声明 fixture**。

具体实现在哪儿：
  · 通用基础设施（配置 / 变量池 / HTTP 底座 / 数据库）→ `src/pytest_framework/`
  · 被测系统专属的测试数据逻辑（前置造数 / 快照差集清理）→ `fixtures/shortlink.py`

⚠️ **别往这个文件里写业务逻辑**。判据：**这段代码需要 pytest 吗？**
   不需要（纯 HTTP 调用、纯数据处理）→ 搬去 `fixtures/`，这里只留 `yield from` 薄壳。
   一个几百行的 conftest 意味着有人在用 Composition Root 装业务逻辑。
"""

import logging
import platform
from pathlib import Path
from typing import Iterator

import pytest

from fixtures.shortlink import cleanup_shortlink_data, prepare_shortlink_data
from pytest_framework.adapters.config import Config
from pytest_framework.adapters.db_checker import DbChecker
from pytest_framework.adapters.execute_case import ExecuteCase
from pytest_framework.entities.constants.logging import LogConfig
from pytest_framework.entities.context.context import Context
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

# allure 的约定（插件注册的选项名 + 它认的文件名）—— 不是我们定的，所以是常量而非魔法值
ALLURE_DIR_OPTION = '--alluredir'
ENVIRONMENT_FILE = 'environment.properties'


# ---------- 通用基础设施：注入给整个会话 ----------


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


# ---------- 被测系统：商用短链平台（Java / Spring Cloud） ----------
#
# 早期还有个 flaskServer 靶场，2026-10-12 已归档到 `archive/`（它是纯内存 mock、
# 没有数据库，「查库校验」那一步教不了）。现在框架只服务短链平台这一个系统。
#
# ⚠️ 下面这几个 fixture 的逻辑都住在 `fixtures/shortlink.py` —— 这里只**声明**。
#    改行为请改那边，别把实现搬回来。


@pytest.fixture(scope='session')
def shortlink_client(config: Config) -> Iterator[HttpClient]:
    """短链平台的 HTTP 客户端。**全仓唯一 `new` 具体实现的地方之一。**

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
    """造短链平台用例要用的**只读**公共前置 —— 实现见 `fixtures/shortlink.py`。"""
    yield from prepare_shortlink_data(shortlink_client, context)


@pytest.fixture(scope='session')
def cleanup_test_data(
    shortlink_client: HttpClient, context: Context, shortlink_login
) -> Iterator[None]:
    """会话结束清掉本次造的数据（快照差集）—— 实现见 `fixtures/shortlink.py`。

    ⚠️ **为什么不做 autouse**：根 conftest 的 autouse fixture 会连 `tests/` 里那批框架
       单测一起触发 —— 它们的目标是「零外部依赖」，被拉去连被测服务就废了（同坑 ⑭）。
       所以**显式挂**在用例文件上。

    依赖 `shortlink_login` 是为了保证 token 已经入池（清理要用它）。
    """
    yield from cleanup_shortlink_data(shortlink_client, context)


# ---------- 报告 ----------


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
