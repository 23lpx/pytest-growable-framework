import pytest

from pytest_framework.entities.context.context import Context
from pytest_framework.entities.context.functions import register
from pytest_framework.entities.context.replacer import resolve_str, resolve_value
from pytest_framework.entities.exception.errors import ContextError


@pytest.fixture
def ctx() -> Context:
    context = Context()
    context.set("token", "9aBc")
    context.set("count", 3)
    context.set("Cookie.access_token", "jwt-abc")
    return context


class TestResolveStr:

    def test_no_placeholder_passthrough(self, ctx: Context) -> None:
        assert resolve_str("plain", ctx) == "plain"

    def test_variable(self, ctx: Context) -> None:
        assert resolve_str("${token}", ctx) == "9aBc"

    def test_dot_path(self, ctx: Context) -> None:
        assert resolve_str("${Cookie.access_token}", ctx) == "jwt-abc"

    def test_whole_placeholder_keeps_type(self, ctx: Context) -> None:
        """整串恰好是一个占位符 → 原类型直传，int 还是 int。

        课程项目在这里用 json.loads 还原，类型忽 int 忽 str，是明确的坑。
        """
        assert resolve_str("${count}", ctx) == 3
        assert isinstance(resolve_str("${count}", ctx), int)

    def test_mixed_placeholder_becomes_str(self, ctx: Context) -> None:
        assert resolve_str("id-${count}", ctx) == "id-3"

    def test_multiple_placeholders(self, ctx: Context) -> None:
        assert resolve_str("${token}-${count}", ctx) == "9aBc-3"

    def test_function_call(self, ctx: Context) -> None:
        """${today()} 这类走函数市场，整串占位符同样保留类型。"""
        assert isinstance(resolve_str("${timestamp()}", ctx), int)
        assert isinstance(resolve_str("${today()}", ctx), str)

    def test_function_args_are_stripped(self, ctx: Context) -> None:
        """${f(a, b)} 的参数要 strip —— 课程项目的第二个参数会带空格。"""

        @register("_join")
        def _join(a: str, b: str) -> str:
            return f"{a}|{b}"

        assert resolve_str("${_join( x , y )}", ctx) == "x|y"

    def test_isolated_dollar_is_not_a_placeholder(self, ctx: Context) -> None:
        """孤立 $ 不该被误判 —— 课程项目用 index('$') 就栽在这。"""
        assert resolve_str("价格是 $100", ctx) == "价格是 $100"
        assert resolve_str("${token} 和 $100", ctx) == "9aBc 和 $100"

    def test_missing_variable_raises(self, ctx: Context) -> None:
        with pytest.raises(ContextError):
            resolve_str("${nope}", ctx)

    def test_unknown_function_raises(self, ctx: Context) -> None:
        with pytest.raises(ContextError):
            resolve_str("${nope()}", ctx)

    def test_nested_placeholder_raises(self, ctx: Context) -> None:
        """嵌套直接报错，不产出半解析的怪字符串。"""
        with pytest.raises(ContextError):
            resolve_str("${token(${count})}", ctx)


class TestResolveValue:

    def test_dict(self, ctx: Context) -> None:
        assert resolve_value({"t": "${token}"}, ctx) == {"t": "9aBc"}

    def test_nested_dict(self, ctx: Context) -> None:
        data = {"outer": {"inner": "${token}"}}
        assert resolve_value(data, ctx) == {"outer": {"inner": "9aBc"}}

    def test_list(self, ctx: Context) -> None:
        assert resolve_value(["${token}", "x"], ctx) == ["9aBc", "x"]

    def test_non_str_untouched(self, ctx: Context) -> None:
        assert resolve_value(200, ctx) == 200
        assert resolve_value(None, ctx) is None

    def test_does_not_mutate_original(self, ctx: Context) -> None:
        """必须产新对象。

        原 case 是 pytest 收集阶段构造、整个 session 共用的，
        就地改会让 --reruns 第二遍跑到脏数据。
        """
        original = {"t": "${token}", "n": 1, "nested": {"k": "${token}"}}
        resolved = resolve_value(original, ctx)

        assert resolved == {"t": "9aBc", "n": 1, "nested": {"k": "9aBc"}}
        assert original == {"t": "${token}", "n": 1, "nested": {"k": "${token}"}}
