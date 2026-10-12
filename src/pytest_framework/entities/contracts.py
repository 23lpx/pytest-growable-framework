"""跨层契约（Protocol）—— 描述「东西长什么样」「能不能取值」。

和 `ports/` 的分工，判据**不是**「像不像接口」，而是**谁依赖它**：

- 被 `entities` 自己用的（`VariableSource` 要当 `Context.parent` 的类型）→ 留这儿
- 被 `usecases` / `adapters` 依赖、而由 `infrastructure` 实现的（`Sender`）→ 进 `ports/`

放反了就会出现「最内层反向依赖外层」。
"""

from typing import Any, Protocol


class CaseLike(Protocol):
    """「一条可执行用例」的契约（门禁）。

    执行器和适配器只依赖它，不依赖具体的 ExecuteCase 类 ——
    只要结构对得上就行，不用显式继承。
    传错对象会在类型检查阶段暴露，而不是跑到一半才发现属性不存在。

    ⚠️ 字段必须和 adapters/execute_case.py 的 ExecuteCase、
    entities/context/replacer.py 的 ResolvedCase 保持一致（**三处同步改**）。
    """

    api_name: str
    url: str
    method: str
    headers: dict
    case_name: str
    data: dict
    validations: list
    extracts: dict
    db_validations: list
    path_params: dict


class ResponseLike(Protocol):
    """「一个 HTTP 响应」该提供的东西（门禁）。

    为什么需要它：adapter 只用得上 status_code / text / json() 三样，
    却 import 了 `requests.Response` —— 那是**最外层的具体库**。
    内层依赖它，等于被绑死在 requests 上（换 httpx 就得改三个 adapter）。

    结构对得上就行、不用继承：`requests.Response` 天然满足，
    单测里的响应桩也满足。
    """

    status_code: int
    text: str

    def json(self) -> Any: ...


class VariableSource(Protocol):
    """「能按点号路径取值」的来源（门禁）。

    `Context` 自己满足它，`adapters/config.py` 的 `Config` 也满足它 ——
    `Context` 的 parent 就是一个 `VariableSource`。这样「变量池」和「配置」
    能拼成一条查找链，而 `Context` 不必知道父级是配置还是别的什么。

    约定：取不到**抛 `ContextError`**、不返回 None —— 同一条链上异常类型一致，
    穿透时就不用做异常转换。

    ⚠️ 它**不搬去 `ports/`**：`Context` 自己就要用它做 `parent` 的类型标注，
    而 `Context` 在 `entities/`（最内层）—— 搬过去会让 entities 反向依赖 ports。
    """

    def get(self, key: str) -> Any: ...

    def exists(self, key: str) -> bool: ...
