import pytest

from framework.context.context import Context
from framework.exception.errors import ContextError


class TestContext:

    def test_set_get_flat(self) -> None:
        ctx = Context()
        ctx.set("token", "abc")
        assert ctx.get("token") == "abc"

    def test_dot_path_auto_creates_middle_layer(self) -> None:
        ctx = Context()
        ctx.set("Cookie.access_token", "jwt-abc")

        assert ctx.get("Cookie.access_token") == "jwt-abc"
        # 中间层能被整块取出来
        assert ctx.get("Cookie") == {"access_token": "jwt-abc"}

    def test_deep_path(self) -> None:
        ctx = Context()
        ctx.set("a.b.c.d", 1)
        assert ctx.get("a.b.c.d") == 1

    def test_get_missing_raises_not_none(self) -> None:
        """取不到必须抛，**不能返回 None**。

        静默返回空值会让「没提取到」伪装成「值本来就是空的」——
        那是课程项目的反面教材。
        """
        ctx = Context()
        with pytest.raises(ContextError):
            ctx.get("nope")

    def test_get_partial_path_raises(self) -> None:
        """路径走一半断了，也要抛，不能返回中间层或 None。"""
        ctx = Context()
        ctx.set("a", 1)
        with pytest.raises(ContextError):
            ctx.get("a.b")

    def test_set_middle_layer_not_dict_raises(self) -> None:
        """先 set("a", 1) 再 set("a.b", 2) —— 明确报错，不静默覆盖。"""
        ctx = Context()
        ctx.set("a", 1)
        with pytest.raises(ContextError):
            ctx.set("a.b", 2)

    def test_exists(self) -> None:
        ctx = Context()
        assert not ctx.exists("x")

        ctx.set("x", 1)
        assert ctx.exists("x")

    def test_overwrite(self) -> None:
        ctx = Context()
        ctx.set("k", 1)
        ctx.set("k", 2)
        assert ctx.get("k") == 2

    def test_value_type_preserved(self) -> None:
        """存进去什么类型，取出来还是什么类型。"""
        ctx = Context()
        ctx.set("count", 3)
        ctx.set("items", [1, 2])
        ctx.set("flag", True)

        assert ctx.get("count") == 3
        assert isinstance(ctx.get("count"), int)
        assert ctx.get("items") == [1, 2]
        assert ctx.get("flag") is True
