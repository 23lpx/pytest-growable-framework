from requests import Response

from framework.client.http_client import HttpClient
from framework.contracts import CaseLike


class RequestHandler:
    """发送请求这一步：把 case 的 method/url/headers/data 交给 HttpClient 发出去。

    只干「发」这一件事 —— 它不认识 yaml、不做断言。

    注意别和 client 层的 HttpClient 混了：那个是「HTTP 底座」（管 session/timeout），
    这个只是用例执行里「发请求」的那一步。
    """

    def __init__(self, base_url: str) -> None:
        self.client = HttpClient(base_url)

    def send(self, case: CaseLike) -> Response:
        return self.client._request(
            method=case.method,
            path=case.url,
            headers=case.headers,
            data=case.data,
        )

    def close(self) -> None:
        self.client.close()
