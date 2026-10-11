import re

import pytest

from pytest_framework.entities.context.functions import FUNCTIONS, call, register
from pytest_framework.entities.exception.errors import ContextError


class TestFunctions:

    def test_builtins_registered(self) -> None:
        assert "today" in FUNCTIONS
        assert "timestamp" in FUNCTIONS

    def test_today_format(self) -> None:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", call("today"))

    def test_timestamp_is_int(self) -> None:
        assert isinstance(call("timestamp"), int)

    def test_unknown_function_raises(self) -> None:
        with pytest.raises(ContextError):
            call("nope")

    def test_register_extends_market(self) -> None:
        """扩展点：加函数只要挂个装饰器，框架别处不用改。"""

        @register("_double")
        def _double(n: str) -> int:
            return int(n) * 2

        assert call("_double", "21") == 42

    def test_function_error_wrapped_as_context_error(self) -> None:
        """函数内部炸了要转成 ContextError 并保留原因，不能原样漏出去。"""

        @register("_boom")
        def _boom() -> None:
            raise RuntimeError("炸了")

        with pytest.raises(ContextError) as exc_info:
            call("_boom")

        assert isinstance(exc_info.value.__cause__, RuntimeError)
