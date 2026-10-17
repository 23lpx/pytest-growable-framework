"""提取这一步：把响应里后续要用的值（token / user_id …）捞出来存进变量池。

**为什么在 `usecases/` 而不是 `adapters/`**：同 `validation.py` —— 它处理的都是
内存里的 dict，不跨任何边界。`jsonpath` 是**算法**，不是外部系统。

（原先它在 `adapters/` 下，会让 `usecases` 反向依赖 `adapters` —— 2026-10-16 挪过来。）
"""

from typing import Any

import jsonpath

from pytest_framework.entities.context.context import Context
from pytest_framework.entities.contracts import CaseLike, ResponseLike
from pytest_framework.entities.exception.errors import ExtractError


class ExtractHandler:
    """按 case.extracts 里的 jsonpath 表达式取值，写进 Context。

    只干「提取」这一件事 —— 怎么发请求、怎么断言都不归它管。
    取不到就抛 ExtractError，**不静默跳过**：
    悄悄跳过会让这条用例看起来是绿的，等症状在下一条用例上爆发，排查时找错地方。
    """

    def extract(self, case: CaseLike, resp: ResponseLike, context: Context) -> None:
        # 提前退出：大多数用例不提取，没必要白解析一遍 JSON
        if not case.extracts:
            return

        data = self._parse(resp)
        for key, expr in case.extracts.items():
            context.set(key, self._pick(data, expr))

    @staticmethod
    def _parse(resp: ResponseLike) -> Any:
        try:
            return resp.json()
        except ValueError as e:
            raise ExtractError(f"响应不是合法 JSON，无法提取: {resp.text[:200]}") from e

    @staticmethod
    def _pick(data: Any, expr: str) -> Any:
        """按 jsonpath 表达式取值。

        ⚠️ jsonpath 库在**无匹配时返回 False**（不是空列表），
        直接取 [0] 会 TypeError —— 所以必须先判类型再判长度。
        课程项目正是在这里被外层 except 吞掉，症状表现为「提取静默失败」。
        """
        result = jsonpath.jsonpath(data, expr)
        if not isinstance(result, list) or not result:
            raise ExtractError(f"jsonpath 没取到值: {expr}")

        return result[0]
