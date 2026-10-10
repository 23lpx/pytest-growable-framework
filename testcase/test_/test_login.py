import pytest
from utils.yaml_to_params import to_login_params


class TestLogin:

    @pytest.mark.parametrize("user_name,passwd,expect_code,expect_msg",to_login_params())
    def test_login(self,api,base_url,user_name,passwd,expect_code,expect_msg):
        client = api('login_cases.yaml',base_url)
        # url = 'http://127.0.0.1:8787/dar/user/login'
        # headers = {
        #     'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
        # }
        data = {
            'user_name': user_name,
            'passwd': passwd
        }

        # resp = requests.post(url, data=data,headers=headers)
        resp = client.post(data=data)
        print(resp.text)
        print(expect_code)
        assert resp.status_code == 200
        assert resp.json().get('msg_code','') == expect_code
        assert expect_msg in resp.json().get('msg',"")

    # @pytest.mark.smoke
    # @pytest.mark.run(order=2)
    # def test_login_success(self,login):
    #     url = 'http://127.0.0.1:8787/dar/user/login'
    #     headers = {
    #         'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
    #     }
    #     data = {
    #         'user_name': 'test01',
    #         'passwd': 'admin123'
    #     }
    #     resp = requests.post(url, data=data,headers=headers)
    #     print(resp.text)
    #     assert resp.status_code == 200
    #     assert resp.json().get('msg') == '登录成功'
    #
    # @pytest.mark.regression
    # @pytest.mark.run(order=1)
    # def test_login_fail(self):
    #     url = 'http://127.0.0.1:8787/dar/user/login'
    #     headers = {
    #         'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
    #     }
    #     data = {
    #         'user_name': 'test01',
    #         'passwd': 'admin1234'
    #     }
    #     resp = requests.post(url, data=data,headers=headers)
    #     print(resp.text)
    #     assert resp.status_code == 200
    #     assert resp.json().get('msg') == '登录失败,用户名或密码错误'

    # @pytest.mark.skip(reason='111')
    # def test_login_locked(self):
    #     pass
    #
    # @pytest.mark.skipif(requests.post('http://127.0.0.1:8787').status_code!=200, reason='222')
    # def test_order_placeholder(self):
    #     pass
    # @pytest.mark.xfail(reason='333')
    # def test_login_v2(self):
    #     assert 2==1