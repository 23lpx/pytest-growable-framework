from requests import Response

from framework.constants.validation import ValidationOp
from framework.contracts import CaseLike
from framework.exception.errors import ValidationError


class ValidationHandler:
    """校验这一步：按 case.validations 里的规则，逐条比对响应。

    只干「比对」这一件事 —— 怎么发请求、怎么提取，都不归它管。
    校验不过抛 ValidationError（不吞），由上层决定测试失败。
    """

    def validate(self, case: CaseLike, resp: Response) -> None:
        try:
            resp_data = resp.json()
        except ValueError as e:
            raise ValidationError(f"响应不是合法 JSON: {resp.text[:200]}") from e

        for validation in case.validations:
            for key, value in validation.items():
                if key == ValidationOp.CONTAINS:
                    if not value.items() <= resp_data.items():
                        raise ValidationError(f"期望响应包含 {value}，实际 {resp_data}")
