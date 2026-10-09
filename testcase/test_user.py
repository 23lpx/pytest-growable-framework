

import pytest
import requests
from common.utils.yaml_to_params import to_user_add_params

class TestUser:

    def test_query_user(self):
        url = 'http://127.0.0.1:8787/dar/user/queryUser'
        headers = {
            'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'
        }
        data = {
            'user_id':'123839387391912'
        }
        resp = requests.post(url,headers=headers,data=data)
        print(resp.text)


    @pytest.mark.parametrize("username,expect_code,expect_msg,token_key",to_user_add_params())
    def test_add_user(self,token,username,expect_code,expect_msg,token_key):
        url = 'http://127.0.0.1:8787/dar/user/addUser'
        headers = {
            'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8',
        }
        result_token = token_key
        print(token_key)
        print(f'token: {token}')
        if token_key == 'valid':
            result_token = token
        elif token_key == 'missing':
            result_token = None
        else:
            result_token = token +"xxxx"
        data = {
            "username": username['user_name'],
            "password": "tset6789890",
            "role_id": 123456789,
            "dates": "2023-12-31",
            "phone": 13800000000,
            "token":result_token
        }
        resp = requests.post(url,headers=headers,data=data)
        print(resp.text)

        assert resp.status_code == 200
        assert resp.json()['msg'] == expect_msg
        assert resp.json()['msg_code'] == expect_code