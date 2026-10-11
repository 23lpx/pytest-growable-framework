from typing import Any, Protocol


class CaseLike(Protocol):
    """「一条可执行用例」的契约（门禁）。

    Runner 和 Handler 只依赖它，不依赖具体的 ExecuteCase 类 ——
    只要结构对得上就行，不用显式继承。
    传错对象会在类型检查阶段暴露，而不是跑到一半才发现属性不存在。

    ⚠️ 字段必须和 adapter/execute_case.py 的 ExecuteCase、context/replacer.py 的
    ResolvedCase 保持一致（**三处同步改**）。
    """

    api_name: str
    url: str
    method: str
    headers: dict
    case_name: str
    data: dict
    validations: list
    extracts: dict


class VariableSource(Protocol):
    """「能按点号路径取值」的来源（门禁）。

    `Context` 自己满足它，`Config` 也满足它 —— `Context` 的 parent 就是一个
    `VariableSource`。这样「变量池」和「配置」能拼成一条查找链，
    而 `Context` 不必知道父级具体是配置还是别的什么。

    约定：取不到**抛 ContextError**、不返回 None。
    同一条链上异常类型一致，穿透时就不用做异常转换。
    """

    def get(self, key: str) -> Any: ...

    def exists(self, key: str) -> bool: ...
