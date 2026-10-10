"""框架单测的公共桩。

注意：这里**故意不调 init_logger()** —— 单测不该往 logs/app.log 里灌数据。
"""

from typing import Any, Callable

import pytest


class FakeResponse:
    """桩响应。

    单测不连被测服务，也**不引新依赖**（responses / requests-mock 都没装）——
    requests.Response 只出现在类型标注里，鸭子类型够用。
    """

    def __init__(
        self,
        payload: Any = None,
        text: str = "",
        status_code: int = 200,
        json_error: bool = False,
    ) -> None:
        self._payload = payload
        self._json_error = json_error
        self.text = text or str(payload)
        self.status_code = status_code

    def json(self) -> Any:
        if self._json_error:
            raise ValueError("桩响应：不是合法 JSON")
        return self._payload


@pytest.fixture
def make_response() -> Callable[..., FakeResponse]:
    """用法：make_response({"msg": "ok"}) / make_response(json_error=True)"""

    def _make(payload: Any = None, **kwargs: Any) -> FakeResponse:
        return FakeResponse(payload, **kwargs)

    return _make
