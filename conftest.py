from typing import Iterator

import pytest

from framework.client.http_client import HttpClient
from framework.infra.logger import init_logger

init_logger()


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
