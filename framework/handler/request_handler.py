from requests import Response

from framework.client.http_client import HttpClient
from framework.contracts import CaseLike


class RequestHandler:
    """发送请求这一步：把 case 的 method/url/headers/data 交给 HttpClient 发出去。

    只干「发」这一件事 —— 它不认识 yaml、不做断言。

    HttpClient 由外面注入（不自己 new），所以它的生命周期不归这里管 ——
    谁创建谁销毁，交给 fixture。

    注意别和 client 层的 HttpClient 混了：那个是「HTTP 底座」，这个只是执行流程里发请求的那一步。
    """

    def __init__(self, client: HttpClient) -> None:
        self.client = client

    def send(self, case: CaseLike) -> Response:
        return self.client._request(
            method=case.method,
            path=case.url,
            headers=case.headers,
            data=case.data,
        )
