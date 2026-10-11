from typing import Any, Callable

import pytest

from pytest_framework.entities.exception.errors import ValidationError
from pytest_framework.adapters.validation import ValidationHandler


class FakeCase:
    """handler 只用到 validations 一个字段。"""

    def __init__(self, validations: list) -> None:
        self.validations = validations


@pytest.fixture
def handler() -> ValidationHandler:
    return ValidationHandler()


class TestContains:

    def test_pass(
        self, handler: ValidationHandler, make_response: Callable[..., Any]
    ) -> None:
        handler.validate(
            FakeCase([{"contains": {"msg": "登录成功"}}]),
            make_response({"msg": "登录成功", "msg_code": 200}),
        )

    def test_pass_when_response_has_extra_keys(
        self, handler: ValidationHandler, make_response: Callable[..., Any]
    ) -> None:
        """响应多几个 key 不影响 —— contains 只看期望提到的那几个。"""
        handler.validate(
            FakeCase([{"contains": {"msg": "ok"}}]),
            make_response({"msg": "ok", "extra": 1, "more": 2}),
        )

    def test_fail_on_value_mismatch(
        self, handler: ValidationHandler, make_response: Callable[..., Any]
    ) -> None:
        with pytest.raises(ValidationError):
            handler.validate(
                FakeCase([{"contains": {"msg": "登录成功"}}]),
                make_response({"msg": "登录失败"}),
            )

    def test_fail_on_missing_key(
        self, handler: ValidationHandler, make_response: Callable[..., Any]
    ) -> None:
        with pytest.raises(ValidationError):
            handler.validate(
                FakeCase([{"contains": {"msg": "ok"}}]), make_response({"code": 200})
            )

    def test_is_exact_not_substring(
        self, handler: ValidationHandler, make_response: Callable[..., Any]
    ) -> None:
        """⚠️ 精确等值，不是子串匹配 —— 见 README 坑 ⑪。

        课程项目的 contains 是子串匹配，两者语义不同，别记混。
        """
        with pytest.raises(ValidationError):
            handler.validate(
                FakeCase([{"contains": {"msg": "新增失败"}}]),
                make_response({"msg": "新增失败，参数缺失或token失效"}),
            )

    def test_type_matters(
        self, handler: ValidationHandler, make_response: Callable[..., Any]
    ) -> None:
        """200 和 '200' 不算相等 —— 类型也参与比较。"""
        with pytest.raises(ValidationError):
            handler.validate(
                FakeCase([{"contains": {"msg_code": 200}}]),
                make_response({"msg_code": "200"}),
            )


class TestGuards:

    def test_unknown_operator_raises(
        self, handler: ValidationHandler, make_response: Callable[..., Any]
    ) -> None:
        """未知操作符必须当场报错 —— 静默跳过会让「yaml 写错」伪装成「用例通过」。"""
        with pytest.raises(ValidationError) as exc:
            handler.validate(FakeCase([{"nope": {}}]), make_response({"a": 1}))

        assert "未知校验操作符" in str(exc.value)

    def test_non_json_response_raises(
        self, handler: ValidationHandler, make_response: Callable[..., Any]
    ) -> None:
        with pytest.raises(ValidationError):
            handler.validate(
                FakeCase([{"contains": {"a": 1}}]),
                make_response(json_error=True, text="<html>error</html>"),
            )

    def test_non_dict_response_raises_not_attribute_error(
        self, handler: ValidationHandler, make_response: Callable[..., Any]
    ) -> None:
        """响应是数组时要抛 ValidationError，**不能**让 AttributeError 逃出去。

        这是修掉的逃逸 bug 的回归保护 —— 逃逸的话 Runner 补不上 case_name，
        报错也看不出是哪条用例挂的。
        """
        with pytest.raises(ValidationError):
            handler.validate(
                FakeCase([{"contains": {"a": 1}}]), make_response([1, 2, 3])
            )

    def test_non_dict_rule_raises(
        self, handler: ValidationHandler, make_response: Callable[..., Any]
    ) -> None:
        """yaml 手误写成 `contains: 登录成功`（少了键值对），要报 ValidationError。"""
        with pytest.raises(ValidationError):
            handler.validate(
                FakeCase([{"contains": "登录成功"}]), make_response({"msg": "登录成功"})
            )


class TestHorizontalExtension:

    def test_new_operator_needs_no_change_to_validate(
        self, make_response: Callable[..., Any]
    ) -> None:
        """水平扩展：加操作符 = 加一个方法 + 表里加一行，`validate()` 一行不动。"""

        class Extended(ValidationHandler):
            _HANDLERS = {**ValidationHandler._HANDLERS, "is_ok": "_is_ok"}

            @staticmethod
            def _is_ok(value: Any, actual: dict) -> None:
                if actual.get("code") != value:
                    raise ValidationError(f"code 应为 {value}，实际 {actual.get('code')}")

        Extended().validate(FakeCase([{"is_ok": 200}]), make_response({"code": 200}))

        with pytest.raises(ValidationError):
            Extended().validate(FakeCase([{"is_ok": 200}]), make_response({"code": 500}))
