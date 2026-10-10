from typing import Protocol


class CaseLike(Protocol):
    """「一条可执行用例」的契约（门禁）。

    Runner 和 Handler 只依赖它，不依赖具体的 ExecuteCase 类 ——
    只要结构对得上就行，不用显式继承。
    传错对象会在类型检查阶段暴露，而不是跑到一半才发现属性不存在。

    ⚠️ 字段必须和 adapter/execute_case.py 的 ExecuteCase 保持一致（两处同步改）。
    """

    api_name: str
    url: str
    method: str
    headers: dict
    case_name: str
    data: dict
    validations: list
