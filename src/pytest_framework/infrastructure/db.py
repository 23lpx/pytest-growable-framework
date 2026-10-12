"""MySQL 底座：`ports.QueryExecutor` 端口的一个实现。

pymysql 的细节全收在这个文件里 —— 换驱动、换库（PostgreSQL 等）只改这里，
依赖端口的 `adapters/db_checker.py` 一行不动。和 `http.py` 对 `Sender`
的关系是同一个套路。

⚠️ 这里**不认识测试概念**：没有 case、没有断言、没有「期望值」。给一条 SQL，
还一堆行，就这些。
"""

from typing import Any, Sequence

import pymysql
from pymysql.cursors import DictCursor

from pytest_framework.entities.exception.errors import DatabaseError


class MySqlExecutor:
    """按配置连一个 MySQL，`query()` 执行查询并返回 `list[dict]`。

    只提供 `query`（`QueryExecutor` 契约只要求这一件事）—— **不提供写库能力**，
    理由见 `ports/query.py` 的 docstring。

    ⚠️ **连接是懒建的**：`__init__` 只记配置，第一条 `query()` 才真连。
    「配了 db 段但这次不跑查库用例」因此零成本 —— 否则 session 级 fixture
    一被求值就建连接，数据库没起会连带**完全不查库的用例**一起崩（真踩过）。
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
    ) -> None:
        # 配置留着 —— 懒连接和断线重连都要用
        self._config: dict[str, Any] = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
        }
        # 先占位、不连 —— 为什么见类 docstring
        self._conn: pymysql.connections.Connection | None = None

    def _connect(self) -> pymysql.connections.Connection:
        """建连接。失败是「环境坏了」，转成 DatabaseError —— 上层只认框架异常，
        不能让 pymysql 的异常原样逃出去。"""
        try:
            return pymysql.connect(
                **self._config,
                charset="utf8mb4",
                # 返回 dict 而不是元组：断言按列名说话，`row.get("phone")` 比
                # `row[2]` 稳得多 —— 后者列顺序一变就错，而且错得很难发现。
                cursorclass=DictCursor,
                # 只读场景不需要事务，开了反而要操心「忘了提交」。
                autocommit=True,
            )
        except pymysql.MySQLError as e:
            c = self._config
            raise DatabaseError(
                f"数据库连接失败: {c['host']}:{c['port']}/{c['database']}"
            ) from e

    def query(
        self, sql: str, params: Sequence[Any] | None = None
    ) -> list[dict[str, Any]]:
        """执行查询，返回所有行。**第一次调用才会真建连接**。"""
        try:
            conn = self._ensure_alive()
            with conn.cursor() as cursor:
                cursor.execute(sql, list(params) if params else None)
                return list(cursor.fetchall())
        except pymysql.MySQLError as e:
            raise DatabaseError(f"查询失败: {sql}") from e

    def _ensure_alive(self) -> pymysql.connections.Connection:
        """返回一个可用连接：没连过就建；连过但被 MySQL 的 wait_timeout 掐掉了
        （两条用例隔久了就会）就按原配置重连一次。

        不用 `ping(reconnect=True)` —— 那个参数已被 pymysql 标记废弃，
        而且重连行为藏在底层；自己写反而清楚。
        """
        if self._conn is None:
            self._conn = self._connect()
            return self._conn

        try:
            self._conn.ping()
        except pymysql.MySQLError:
            self._conn = self._connect()
        return self._conn

    def close(self) -> None:
        """关连接。谁创建谁销毁 —— 由 conftest 的 fixture 在会话结束时调用。

        从没查过库（`_conn` 还是 None）就直接返回 —— 什么都没建，没什么可关。
        """
        if self._conn is not None:
            self._conn.close()
