import platform
from pathlib import Path
from typing import Iterator

import pytest

from pytest_framework.adapters.db_checker import DbChecker
from pytest_framework.adapters.execute_case import ExecuteCase
from pytest_framework.infrastructure.http import HttpClient
from pytest_framework.infrastructure.db import MySqlExecutor
from pytest_framework.adapters.config import Config
from pytest_framework.entities.context.context import Context
from pytest_framework.infrastructure.logging.logger import init_logger
from pytest_framework.infrastructure.logging.masking import configure_masking
from pytest_framework.infrastructure.path import _project_root
from pytest_framework.entities.model.case_model import CaseModel
from pytest_framework.usecases.case_runner import CaseRunner

init_logger()

LOGIN_CASES = '/data/api/login_cases.yaml'

# 第二个被测系统（短链平台）的登录用例 —— 和上面那个分开，两边 token 机制不同
SHORTLINK_LOGIN_CASES = '/data/api_shortlink/login_post_account_login.yaml'

# allure 的约定（插件注册的选项名 + 它认的文件名）—— 不是我们定的，所以是常量而非魔法值
ALLURE_DIR_OPTION = '--alluredir'
ENVIRONMENT_FILE = 'environment.properties'


def pytest_addoption(parser: pytest.Parser) -> None:
    """把「被测服务地址」做成命令行参数 —— 临时指到别的环境不用改配置。

    base_url 不敏感、每个环境都可能不同，命令行改起来最快；不给默认值，
    没传就落到 config/config.yaml（优先级：命令行 > 环境变量 > 配置）。
    账号密码这类敏感的**不能**上命令行（会进 shell history / CI 日志），
    只走配置文件 / 环境变量。
    """
    parser.addoption(
        "--base-url",
        default=None,
        help="被测服务地址（不传则用 config/config.yaml 里的 base_url）",
    )


@pytest.fixture(scope='session')
def config() -> Config:
    """整个会话共用的配置。

    **懒加载**：session 级 fixture 都是「第一次有人要才求值」—— 所以真正加载的时机
    是**第一条用例开始跑之前**，不是进程启动时。副作用是好的：只跑框架单测
    （`pytest tests/`）根本不会碰配置文件。

    加载完就定死：之后只读，跑的过程中不再变（所以要换环境只能重跑）。

    加载失败（文件没了 / 格式错）抛 ConfigError —— 配置坏了是硬错误，让它喊出来。

    顺手把**脱敏配置**喂给日志层：值特征随被测系统变（短链平台的 token 长什么样，
    flaskServer 的 token 长什么样，各不一样），归配置最合适。放在这里而不是模块
    导入时读，是为了让 `pytest tests/` 跑框架单测时压根不碰配置文件。
    """
    cfg = Config.load()
    configure_masking(
        mode=cfg.get("masking.mode"),
        value_patterns=cfg.get("masking.value_patterns") or [],
    )
    return cfg


@pytest.fixture(scope='session')
def base_url(request: pytest.FixtureRequest, config: Config) -> str:
    """命令行 --base-url 优先，没传就用配置里的。"""
    return request.config.getoption("--base-url") or config.get("base_url")


@pytest.fixture(scope='session')
def client(base_url: str, config: Config) -> Iterator[HttpClient]:
    """整个测试会话共用一个 HttpClient（含 session），跑完再关 —— 谁创建谁销毁。

    session 级是为了**连接复用**（keep-alive）：整个会话建一次连接、跑完所有用例，
    比每条用例新建省得多。不是为了图 cookie —— 本项目鉴权走 token 字段，不靠 cookie。

    超时从配置读：不同环境网速差很多，写死在代码里换环境就得改代码。
    """
    http = HttpClient(base_url, timeout=config.get("http.timeout"))
    yield http
    http.close()


@pytest.fixture(scope='session')
def context(config: Config) -> Context:
    """整个会话共用一个变量池，**父级挂配置**。

    挂父级是为了让 ${...} 只有一个入口：`${token}` 查变量层（提取来的），
    `${login.username}` 落到配置层。用例作者不用区分两套语法。
    配置层是只读的 —— 用例 set 同名 key 只会写进自己层，覆盖不了配置。

    必须是 session 级：跨用例关联要共享，function / module 级每次重置就没法关联了。
    纯内存对象、没有资源要释放，所以不用 yield 收尾。

    ⚠️ 变量池是**进程内**的，开了 -n 分布式时每个 worker 各有一份，
    跨用例关联会失效 —— 有依赖的用例集不要开 -n。
    """
    return Context(parent=config)


@pytest.fixture(scope='session')
def login(context: Context, client: HttpClient) -> None:
    """前置登录：整个会话只登一次，把 token 写进变量池。

    依赖已登录状态的用例，声明这个 fixture 就行 —— 比「靠用例执行顺序」可靠得多。
    顺序不可靠的原因：用例的收集顺序由 pytest 定（文件名字典序 / 参数化列表序），
    "登录先跑"根本不成立。

    取 login_cases 的第一条（成功登录那条，它带 extract）。
    """
    login_case = ExecuteCase.from_model(CaseModel(LOGIN_CASES))[0]
    CaseRunner(client, context).run(login_case)


# ---------- 第二个被测系统：商用短链平台 ----------
@pytest.fixture(scope='session')
def shortlink_client(config: Config) -> Iterator[HttpClient]:
    """短链平台专用客户端。

    **为什么不复用 `client`**：那个的 base_url 是 flaskServer。两个被测系统同时
    存在，各自一个客户端、各自一个 base_url，互不干扰 —— 和「一套变量池挂不同
    父级」是同一个思路：共用的是机制，分开的是数据。

    session 级同样是为了连接复用。
    """
    http = HttpClient(
        config.get("shortlink.base_url"), timeout=config.get("http.timeout")
    )
    yield http
    http.close()


@pytest.fixture(scope='session')
def shortlink_login(shortlink_client: HttpClient, context: Context) -> None:
    """短链平台登录：整个会话只登一次，token 写进变量池。

    和 flaskServer 的 `login` fixture 是**同一个套路**（跑一条带 extract 的用例），
    但走的是**不同的客户端**和**不同的登录接口**。

    ⚠️ 短链平台的 token 放**请求头**（`token: <JWT>`），不是表单参数 ——
    所以用例里要写成 `headers: {token: "${token}"}`。
    """
    login_case = ExecuteCase.from_model(CaseModel(SHORTLINK_LOGIN_CASES))[0]
    CaseRunner(shortlink_client, context).run(login_case)


@pytest.fixture(scope='session')
def db_checker(config: Config) -> Iterator[DbChecker | None]:
    """查库校验器 —— 库校验那条路的入口。

    **没配 db 就返回 None**：纯接口用例照样跑，不会被数据库的可用性牵连。
    只有声明了 `db:` 断言的用例才会真去查、真报错。

    ⚠️ 光靠 fixture 的懒加载**挡不住**数据库不可用：`cases/test_api.py` 把
    `db_checker` 写在 `test_api()` 签名上，参数化展开出的**每条**用例都会拉它，
    所以它必然被求值。真正让"不查库的用例零成本"的是 `MySqlExecutor` 的
    **懒连接**（`__init__` 只记配置，第一条 `query()` 才连）—— 求值这个 fixture
    只造一个空壳对象，一条 TCP 都不会建；数据库真挂了，报错只会落在
    **声明了 `db:` 的用例**上。

    和 `client` 一样：session 级 + 谁创建谁销毁（连接复用，跑完关掉）。
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
    这种压根不出报告的场景也躲不掉（配置一坏，84 条单测全 ERROR）。
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
        f'base_url={config.get("base_url")}',
        f'http.timeout={config.get("http.timeout")}',
        f'login.username={config.get("login.username")}',
        f'python={platform.python_version()}',
    ]
    (path / ENVIRONMENT_FILE).write_text('\n'.join(lines), encoding='utf-8')
