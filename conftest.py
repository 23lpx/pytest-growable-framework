import platform
from pathlib import Path
from typing import Iterator

import pytest

from framework.adapter.execute_case import ExecuteCase
from framework.client.http_client import HttpClient
from framework.config import Config
from framework.context.context import Context
from framework.infra.logger import init_logger
from framework.infra.path import _project_root
from framework.model.case_model import CaseModel
from framework.runner.case_runner import CaseRunner

init_logger()

LOGIN_CASES = '/data/api/login_cases.yaml'

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
    """
    return Config.load()


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
