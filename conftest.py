from typing import Iterator

import pytest

from framework.adapter.execute_case import ExecuteCase
from framework.client.http_client import HttpClient
from framework.context.context import Context
from framework.infra.logger import init_logger
from framework.model.case_model import CaseModel
from framework.runner.case_runner import CaseRunner

init_logger()

LOGIN_CASES = '/data/login_cases.yaml'


@pytest.fixture(scope='session')
def base_url() -> str:
    test_url = 'http://127.0.0.1:8787'
    return test_url


@pytest.fixture(scope='session')
def client(base_url: str) -> Iterator[HttpClient]:
    """整个测试会话共用一个 HttpClient（含 session），跑完再关 —— 谁创建谁销毁。

    session 级是为了**连接复用**（keep-alive）：整个会话建一次连接、跑完所有用例，
    比每条用例新建省得多。不是为了图 cookie —— 本项目鉴权走 token 字段，不靠 cookie。
    """
    http = HttpClient(base_url)
    yield http
    http.close()


@pytest.fixture(scope='session')
def context() -> Context:
    """整个会话共用一个变量池。

    必须是 session 级：跨用例关联要共享，function / module 级每次重置就没法关联了。
    纯内存对象、没有资源要释放，所以不用 yield 收尾。

    ⚠️ 变量池是**进程内**的，开了 -n 分布式时每个 worker 各有一份，
    跨用例关联会失效 —— 有依赖的用例集不要开 -n。
    """
    return Context()


@pytest.fixture(scope='session')
def login(context: Context, client: HttpClient) -> None:
    """前置登录：整个会话只登一次，把 token 写进变量池。

    依赖已登录状态的用例，声明这个 fixture 就行 —— 比「靠用例执行顺序」可靠得多。
    顺序不可靠的原因：pytest 按**文件名字典序**收集用例，
    test_add_user.py 会排在 test_login.py 前面（a < l），"登录先跑"根本不成立。

    取 login_cases 的第一条（成功登录那条，它带 extract）。
    """
    login_case = ExecuteCase.from_model(CaseModel(LOGIN_CASES))[0]
    CaseRunner(client, context).run(login_case)
