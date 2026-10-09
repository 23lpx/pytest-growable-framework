from platform import python_compiler

import pytest
import requests

from common.utils.api_service import ApiService

from common.utils.logger import init_logger

init_logger()

@pytest.fixture(scope='session',name='token')
def login():
    url = 'http://127.0.0.1:8787/dar/user/login'
    headers = {'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'}
    data = {
        'user_name': 'test01',
        'passwd': 'admin123'
    }
    resp = requests.post(url=url,headers=headers,data=data)
    print(resp.json())
    assert resp.status_code == 200
    assert resp.json()['msg'] == '登录成功'
    return resp.json()['token']

@pytest.fixture(scope='session')
def base_url():
    test_url = 'http://127.0.0.1:8787'
    return test_url

@pytest.fixture(scope='function')
def api(request):
    opened = []                       # 记录本用例创建的所有实例

    def maker(test_file_name,base_url):
        svc = ApiService(test_file_name,base_url)
        opened.append(svc)
        return svc

    yield maker

    for svc in reversed(opened):      # 用例结束（含报错）自动清理
        svc.close()

@pytest.fixture(autouse=True, scope="session")
def _show_logger_tree(request):
    yield
    from logging_tree import printout
    print("\n===== Logger Tree =====")
    printout()