"""查询端口（Port）：定义「把一条 SQL 打出去、拿回若干行」这件事。

和 `ports/sender.py` 完全对称 —— **内层定契约、外层实现**：
`infrastructure/db.py` 的 `MySqlExecutor` 是它的一个实现，由 `conftest` 注入。
所以换 pymysql / SQLAlchemy、甚至换成查别的存储，依赖它的
`adapters/db_checker.py` 一行不用改。
"""

from typing import Any, Protocol, Sequence


class QueryExecutor(Protocol):
    """「执行一条查询、拿回若干行」（门禁）。

    ⚠️ **只读**：只开 `query`、不开 `execute`。实测里查库只有「确认一下」这一个
    用途，而让框架能改库等于给测试发了把枪 —— 造数据 / 清理该走别的手段
    （fixture、外部脚本），不该混进断言链路。真要写库时再加，别提前开。

    ⚠️ 和 `Sender` 同理，签名故意是**纯值**（sql / params），不是「DB 期望」的
    数据结构 —— 「查库」这件事不该认识「断言长什么样」。

    返回 `list[dict]`（列名 -> 值），不是元组列表：断言要按列名说话，
    靠下标对列名属于自找麻烦。
    """

    def query(
        self, sql: str, params: Sequence[Any] | None = None
    ) -> list[dict[str, Any]]: ...
