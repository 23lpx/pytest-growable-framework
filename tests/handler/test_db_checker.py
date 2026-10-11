"""DbChecker 的单测 —— **全程用桩，不碰任何真库**。

「能用桩把这一层测透」本身就是分层生效的证据：DbChecker 依赖的是
`ports.QueryExecutor` 这个端口，不是 pymysql。真库那条路由
`infrastructure/db.py` 单独验证（那是另一件事：证明实现符合契约）。
"""

from typing import Any, Sequence

import pytest

from pytest_framework.adapters.db_checker import DbChecker
from pytest_framework.entities.exception.errors import DatabaseError, ValidationError


class FakeDb:
    """桩：记下每次的 SQL 和参数，返回预置的行。

    它**就是** `QueryExecutor` 契约的一个合法实现 —— 不需要继承什么、
    也不需要 `implements`，有 `query` 方法即可（结构化类型）。
    """

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows if rows is not None else []
        self.calls: list[tuple[str, list[Any]]] = []

    def query(
        self, sql: str, params: Sequence[Any] | None = None
    ) -> list[dict[str, Any]]:
        self.calls.append((sql, list(params or [])))
        return self.rows

    @property
    def last_sql(self) -> str:
        return self.calls[-1][0]

    @property
    def last_params(self) -> list[Any]:
        return self.calls[-1][1]


@pytest.fixture
def fake_db() -> FakeDb:
    return FakeDb()


@pytest.fixture
def checker(fake_db: FakeDb) -> DbChecker:
    return DbChecker(fake_db)


class TestSqlGeneration:
    """yaml 里写的是「是什么」，SQL 是这一层生成的「怎么做」。"""

    def test_builds_select_from_declaration(
        self, checker: DbChecker, fake_db: FakeDb
    ) -> None:
        fake_db.rows = [{"phone": "13800000000"}]
        checker.check(
            [
                {
                    "table": "user",
                    "where": {"username": "u1"},
                    "expect": {"phone": "13800000000"},
                }
            ]
        )
        assert fake_db.last_sql == "SELECT `phone` FROM `user` WHERE `username` = %s"
        assert fake_db.last_params == ["u1"]

    def test_values_go_to_params_not_into_sql(
        self, checker: DbChecker, fake_db: FakeDb
    ) -> None:
        """值走参数化，SQL 里不出现字面值 —— 顺带挡住引号把语句拼坏。"""
        fake_db.rows = [{"_exists": 1}]  # 让 check 能走完；本类只关心 SQL 长什么样
        checker.check([{"table": "user", "where": {"username": "o'brien"}}])
        assert "o'brien" not in fake_db.last_sql
        assert fake_db.last_params == ["o'brien"]

    def test_multiple_conditions_joined_by_and(
        self, checker: DbChecker, fake_db: FakeDb
    ) -> None:
        fake_db.rows = [{"_exists": 1}]
        checker.check([{"table": "user", "where": {"a": 1, "b": 2}}])
        assert fake_db.last_sql == (
            "SELECT 1 AS _exists FROM `user` WHERE `a` = %s AND `b` = %s"
        )
        assert fake_db.last_params == [1, 2]

    def test_where_is_optional(self, checker: DbChecker, fake_db: FakeDb) -> None:
        fake_db.rows = [{"a": 1}]
        checker.check([{"table": "user", "expect": {"a": 1}}])
        assert fake_db.last_sql == "SELECT `a` FROM `user`"

    def test_only_selects_expected_columns(
        self, checker: DbChecker, fake_db: FakeDb
    ) -> None:
        """不 `SELECT *` —— 期望里提到哪几列就只查哪几列。"""
        fake_db.rows = [{"a": 1, "b": 2}]
        checker.check([{"table": "user", "expect": {"a": 1, "b": 2}}])
        assert fake_db.last_sql.startswith("SELECT `a`, `b` FROM")


class TestMatch:
    def test_matching_row_passes(self, checker: DbChecker, fake_db: FakeDb) -> None:
        fake_db.rows = [{"phone": "13800000000"}]
        checker.check([{"table": "user", "expect": {"phone": "13800000000"}}])

    def test_any_row_among_many_passes(
        self, checker: DbChecker, fake_db: FakeDb
    ) -> None:
        """多行是常态，**只要有一行对上**就算过。"""
        fake_db.rows = [
            {"phone": "111"},
            {"phone": "13800000000"},
            {"phone": "222"},
        ]
        checker.check([{"table": "user", "expect": {"phone": "13800000000"}}])

    def test_value_mismatch_fails(self, checker: DbChecker, fake_db: FakeDb) -> None:
        fake_db.rows = [{"phone": "13800000000"}]
        with pytest.raises(ValidationError):
            checker.check([{"table": "user", "expect": {"phone": "999"}}])

    def test_one_bad_column_fails_the_whole_row(
        self, checker: DbChecker, fake_db: FakeDb
    ) -> None:
        """expect 里的列要**全部**对上，对上一半不算过。"""
        fake_db.rows = [{"a": 1, "b": "wrong"}]
        with pytest.raises(ValidationError):
            checker.check([{"table": "user", "expect": {"a": 1, "b": "right"}}])

    def test_extra_columns_in_result_do_not_matter(
        self, checker: DbChecker, fake_db: FakeDb
    ) -> None:
        """查回来的行多几列无所谓 —— 只看期望提到的那几列。"""
        fake_db.rows = [{"a": 1, "extra": "x"}]
        checker.check([{"table": "user", "expect": {"a": 1}}])

    def test_no_row_at_all_fails(self, checker: DbChecker, fake_db: FakeDb) -> None:
        fake_db.rows = []
        with pytest.raises(ValidationError):
            checker.check([{"table": "user", "expect": {"a": 1}}])


class TestExpectEmpty:
    """expect 不写 = 只断言「查得到」。"""

    def test_row_exists_passes(self, checker: DbChecker, fake_db: FakeDb) -> None:
        fake_db.rows = [{"_exists": 1}]
        checker.check([{"table": "user", "where": {"username": "u1"}}])

    def test_nothing_found_fails(self, checker: DbChecker, fake_db: FakeDb) -> None:
        fake_db.rows = []
        with pytest.raises(ValidationError):
            checker.check([{"table": "user", "where": {"username": "u1"}}])


class TestGuards:
    def test_missing_table_raises_database_error(
        self, checker: DbChecker
    ) -> None:
        with pytest.raises(DatabaseError) as exc:
            checker.check([{"where": {"a": 1}}])
        assert "table" in str(exc.value)

    def test_illegal_identifier_rejected(self, checker: DbChecker) -> None:
        """表名/列名不能参数化，只能自己守 —— 奇怪的一律当场抛。"""
        with pytest.raises(DatabaseError):
            checker.check([{"table": "user; DROP TABLE user"}])

    def test_illegal_column_rejected(self, checker: DbChecker) -> None:
        with pytest.raises(DatabaseError):
            checker.check([{"table": "user", "expect": {"bad name": 1}}])

    def test_where_must_be_mapping(self, checker: DbChecker) -> None:
        with pytest.raises(DatabaseError):
            checker.check([{"table": "user", "where": "username=1"}])

    def test_fail_fast_stops_at_first_failure(
        self, checker: DbChecker, fake_db: FakeDb
    ) -> None:
        """第一条挂了就不跑第二条 —— 后面的失败多半是它的余波。"""
        fake_db.rows = []
        with pytest.raises(ValidationError):
            checker.check(
                [
                    {"table": "user", "where": {"a": 1}},
                    {"table": "user", "where": {"b": 2}},
                ]
            )
        assert len(fake_db.calls) == 1

    def test_runs_every_expectation_when_all_pass(
        self, checker: DbChecker, fake_db: FakeDb
    ) -> None:
        fake_db.rows = [{"_exists": 1}]
        checker.check(
            [
                {"table": "user", "where": {"a": 1}},
                {"table": "order", "where": {"b": 2}},
            ]
        )
        assert len(fake_db.calls) == 2
