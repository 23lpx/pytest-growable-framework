"""发送端口（Port）：定义「能把一个请求发出去」这件事。

**内层定契约、外层实现** —— `infrastructure/http.py` 的 `HttpClient` 是它的一个
实现，由 `conftest` 注入。所以换 HTTP 库、甚至换成别的传输方式，
依赖它的 `adapters/request.py` 和 `usecases/case_runner.py` 一行不用改。
"""

from typing import Any, Protocol

from pytest_framework.entities.contracts import ResponseLike


class Sender(Protocol):
    """「能把一个请求发出去」（门禁）。

    ⚠️ 签名故意是**纯值**（method / path / **kwargs），不是 `CaseLike` ——
    「发送」这件事不该认识「测试用例」这个概念。
    """

    def request(self, method: str, path: str, **kwargs: Any) -> ResponseLike: ...
