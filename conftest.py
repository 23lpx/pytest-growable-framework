import pytest

from framework.infra.logger import init_logger

init_logger()


@pytest.fixture(scope='session')
def base_url() -> str:
    test_url = 'http://127.0.0.1:8787'
    return test_url
