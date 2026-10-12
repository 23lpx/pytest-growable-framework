from typing import Any, Callable

import pytest

from pytest_framework.entities.context.context import Context
from pytest_framework.entities.exception.errors import ExtractError
from pytest_framework.adapters.extract import ExtractHandler


class FakeCase:
    """handler 只用到 extracts 一个字段，桩对象有它就够（Protocol 是结构匹配）。"""

    def __init__(self, extracts: dict) -> None:
        self.extracts = extracts


@pytest.fixture
def handler() -> ExtractHandler:
    return ExtractHandler()


class TestExtract:

    def test_no_extracts_does_nothing(
        self, handler: ExtractHandler, make_response: Callable[..., Any]
    ) -> None:
        ctx = Context()
        handler.extract(FakeCase({}), make_response({"token": "abc"}), ctx)

        assert not ctx.exists("token")

    def test_jsonpath_hit(
        self, handler: ExtractHandler, make_response: Callable[..., Any]
    ) -> None:
        ctx = Context()
        handler.extract(
            FakeCase({"token": "$.token"}),
            make_response({"token": "abc", "msg": "ok"}),
            ctx,
        )

        assert ctx.get("token") == "abc"

    def test_nested_jsonpath(
        self, handler: ExtractHandler, make_response: Callable[..., Any]
    ) -> None:
        """jsonpath 能挖到任意深度 —— 这就是 P0「定位嵌套字段」的落点。"""
        ctx = Context()
        handler.extract(
            FakeCase({"t": "$.data.user.token"}),
            make_response({"data": {"user": {"token": "deep"}}}),
            ctx,
        )

        assert ctx.get("t") == "deep"

    def test_multiple_extracts(
        self, handler: ExtractHandler, make_response: Callable[..., Any]
    ) -> None:
        ctx = Context()
        handler.extract(
            FakeCase({"token": "$.token", "uid": "$.userId"}),
            make_response({"token": "a", "userId": 42}),
            ctx,
        )

        assert ctx.get("token") == "a"
        assert ctx.get("uid") == 42

    def test_type_preserved(
        self, handler: ExtractHandler, make_response: Callable[..., Any]
    ) -> None:
        """jsonpath 返回的是原生类型，不做字符串化。"""
        ctx = Context()
        handler.extract(FakeCase({"n": "$.n"}), make_response({"n": 200}), ctx)

        assert ctx.get("n") == 200
        assert isinstance(ctx.get("n"), int)

    def test_no_match_raises_not_silent(
        self, handler: ExtractHandler, make_response: Callable[..., Any]
    ) -> None:
        """jsonpath 无匹配时返回 False（不是空列表）—— 必须抛错，不能静默。

        这是课程项目最典型的坑：异常被外层 except 吞掉，
        表现为「提取悄悄失败了」，等症状在下一条用例上爆发。
        """
        ctx = Context()

        with pytest.raises(ExtractError):
            handler.extract(
                FakeCase({"token": "$.nope"}), make_response({"token": "abc"}), ctx
            )

        assert not ctx.exists("token")

    def test_non_json_response_raises(
        self, handler: ExtractHandler, make_response: Callable[..., Any]
    ) -> None:
        ctx = Context()

        with pytest.raises(ExtractError):
            handler.extract(
                FakeCase({"t": "$.t"}),
                make_response(json_error=True, text="<html>error</html>"),
                ctx,
            )

    def test_extract_key_supports_dot_path(
        self, handler: ExtractHandler, make_response: Callable[..., Any]
    ) -> None:
        """extract 的 key 也走点号路径 —— 提取值直接落进多级结构里。"""
        ctx = Context()
        handler.extract(
            FakeCase({"Cookie.access_token": "$.token"}),
            make_response({"token": "jwt"}),
            ctx,
        )

        assert ctx.get("Cookie.access_token") == "jwt"
