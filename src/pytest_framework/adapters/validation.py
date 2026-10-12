from typing import Any, Callable

from pytest_framework.entities.constants.validation import ValidationOp
from pytest_framework.entities.contracts import CaseLike, ResponseLike
from pytest_framework.entities.exception.errors import ValidationError


class ValidationHandler:
    """校验这一步：按 case.validations 里的规则，逐条比对响应。

    只干「比对」这一件事 —— 怎么发请求、怎么提取，都不归它管。
    校验不过抛 ValidationError（不吞），由上层决定测试失败。

    加操作符是**水平扩展**：写一个 `_xxx(value, actual)` 方法 + 在 `_HANDLERS`
    里加一行，`validate()` 本身一行不用动。
    """

    # 操作符 -> 处理方法名。加新操作符只需在这里加一行。
    _HANDLERS: dict[str, str] = {
        ValidationOp.CONTAINS: "_contains",
    }

    def validate(self, case: CaseLike, resp: ResponseLike) -> None:
        actual = self._parse(resp)

        for validation in case.validations:
            for key, value in validation.items():
                # 未知操作符当场报错，不静默跳过 —— 静默会让「yaml 写错操作符名」
                # 伪装成「用例通过」
                handler: Callable[..., None] | None = getattr(
                    self, self._HANDLERS.get(key, ""), None
                )
                if handler is None:
                    raise ValidationError(f"未知校验操作符: {key}")

                handler(value, actual)

    @staticmethod
    def _parse(resp: ResponseLike) -> dict:
        """响应必须是 JSON 对象。

        这一步的守卫是必需的：少了它，响应是数组/标量时下面的 .items() 会抛
        AttributeError，直接逃出框架的异常体系（不是 ValidationError），
        Runner 那边也补不上 case_name 上下文。
        """
        try:
            data = resp.json()
        except ValueError as e:
            raise ValidationError(f"响应不是合法 JSON: {resp.text[:200]}") from e

        if not isinstance(data, dict):
            raise ValidationError(
                f"响应不是 JSON 对象，无法校验: {type(data).__name__}"
            )
        return data

    @staticmethod
    def _contains(expected: Any, actual: dict) -> None:
        """要求响应**精确包含** expected 里每一个键值对。

        ⚠️ 是精确等值，不是子串匹配：期望 `{'msg': '新增成功'}` 时，
        实际 `'新增成功，用户已存在'` **不算通过**。写 yaml 要写完整消息。
        """
        if not isinstance(expected, dict):
            raise ValidationError(f"contains 的规则值必须是键值对: {expected!r}")

        # 收集没对上的，比单看 True/False 多给出「差在哪」
        unmatched = {k: v for k, v in expected.items() if actual.get(k) != v}
        if unmatched:
            raise ValidationError(f"期望响应包含 {expected}，实际 {actual}")
