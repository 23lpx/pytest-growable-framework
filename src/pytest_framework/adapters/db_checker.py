"""数据库校验：把「声明式的库期望」翻成 SQL，跑一遍，比对。

⚠️ yaml 里**不写 SQL** —— 只写「查哪张表、什么条件、期望什么」，SQL 是
「怎么做」，由这一层生成。这不是洁癖：SQL 一旦进了 yaml，用例就绑死在
表结构上，改个字段名要翻遍所有数据文件，而且「测什么」被埋进了实现细节里。
"""

import re
from typing import Any, Sequence

from pytest_framework.entities.constants.db import DbKey
from pytest_framework.entities.exception.errors import DatabaseError, ValidationError
from pytest_framework.ports.query import QueryExecutor

# 表名 / 列名**不能参数化**（SQL 参数化只管值），只能拼进语句 —— 所以要自己守住
# 入口。挡的是「yaml 手滑写出奇怪东西」，不是防注入（数据文件是可信的），
# 但顺手也把注入挡了。
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# 失败信息里最多回显几行 —— 全量回显会把真正的原因淹没在噪音里。
_MAX_ROWS_IN_MSG = 5


def _ident(name: Any) -> str:
    """校验并包裹标识符。非法就抛，**不静默转义**。"""
    if not isinstance(name, str) or not _IDENTIFIER.match(name):
        raise DatabaseError(f"非法表名/列名: {name!r}（只允许字母、数字、下划线）")
    return f"`{name}`"


class DbChecker:
    """查库校验这一步。

    只干「生成 SQL -> 跑 -> 比对」三件事 —— 连什么库、怎么连都不归它管
    （那是 `ports.QueryExecutor` 的实现的事，由 conftest 注入）。

    异常分工：**库本身出问题**（连不上 / 表名列名非法）抛 `DatabaseError`；
    **查到了但和期望对不上**才抛 `ValidationError`。
    """

    def __init__(self, executor: QueryExecutor) -> None:
        self._executor = executor

    def check(self, expectations: Sequence[dict[str, Any]]) -> None:
        """逐条比对。**第一条不过就停**（fail-fast）—— 后面的失败多半是它的余波，
        全跑完只会让真正的原因淹在噪音里。"""
        for expectation in expectations:
            self._check_one(expectation)

    def _check_one(self, expectation: dict[str, Any]) -> None:
        table = expectation.get(DbKey.TABLE)
        where = expectation.get(DbKey.WHERE) or {}
        expect = expectation.get(DbKey.EXPECT) or {}

        if not table:
            raise DatabaseError(f"db 断言缺少 {DbKey.TABLE}: {expectation!r}")
        if not isinstance(where, dict) or not isinstance(expect, dict):
            raise DatabaseError(
                f"db 断言的 {DbKey.WHERE} / {DbKey.EXPECT} 必须是键值对: {expectation!r}"
            )

        rows = self._executor.query(*self._build_sql(table, where, expect))

        # expect 为空 = 「只要查得到就算过」—— 常见于「接口说新增成功，库里确实多了
        # 这一条」这种不关心具体值的断言。
        if not expect:
            if not rows:
                raise ValidationError(
                    f"库断言不通过：{table} 里 where={where} 一行都没查到"
                )
            return

        # 只要**有一行**完全对上就算过 —— 多行是常态（比如按 user_id 查出一串记录），
        # 要求「所有行都匹配」会把正常场景判成失败。
        for row in rows:
            if all(row.get(col) == want for col, want in expect.items()):
                return

        shown = rows[:_MAX_ROWS_IN_MSG]
        suffix = f"（共 {len(rows)} 行，已截断）" if len(rows) > _MAX_ROWS_IN_MSG else ""
        raise ValidationError(
            f"库断言不通过：{table} 里 where={where} 没有一条匹配 {expect}；"
            f"实际查到 {shown}{suffix}"
        )

    @staticmethod
    def _build_sql(
        table: str, where: dict[str, Any], expect: dict[str, Any]
    ) -> tuple[str, list[Any]]:
        """生成 `SELECT 期望的列 FROM 表 WHERE 条件`，条件值一律走参数化。

        只 SELECT 期望里提到的列，不 `SELECT *` —— 既省 I/O，也让「比对哪几列」
        这件事在 SQL 里就是明摆着的。
        """
        columns = ", ".join(_ident(col) for col in expect) if expect else "1 AS _exists"
        sql = f"SELECT {columns} FROM {_ident(table)}"
        if not where:
            return sql, []

        conditions = " AND ".join(f"{_ident(col)} = %s" for col in where)
        # dict 保序，所以 where 的 key 顺序和 values 顺序是对上的。
        return f"{sql} WHERE {conditions}", list(where.values())
