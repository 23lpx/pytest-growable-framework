from typing import Any

from pytest_framework.entities.constants.context import PathSep
from pytest_framework.entities.contracts import VariableSource
from pytest_framework.entities.exception.errors import ContextError


class Context:
    """内存变量池：存提取到的值，供后续用例引用。

    为什么不落文件（课程项目就是往 extract.yaml 里写的）：
    文件在 `-n` 分布式下会被多个进程互相踩，还要额外清理；
    跨用例传值本质是内存问题，不该过磁盘。

    可以挂一个父级（`parent`）拼成查找链：**自己层查不到就去问父级**。
    实际用法是 `Context(parent=config)` —— 上层放用例提取的动态变量，
    底层放环境配置，用例作者只用一套 `${...}` 语法。
    父级是只读的：`set` 只写自己层，配置**不可能被用例覆盖**。

    多级 key 用点号路径（Cookie.access_token_cookie），深度不限。
    取不到一律抛 ContextError —— **不返回 None**：
    静默返回空值会让「没提取到」伪装成「值本来就是空的」，排查时找错地方。
    """

    def __init__(self, parent: VariableSource | None = None) -> None:
        self._data: dict[str, Any] = {}
        self._parent = parent

    def set(self, key: str, value: Any) -> None:
        """写入变量。多级 key 的中间层不存在时会自动建好。

        只写自己这一层 —— 父级（配置）插不进来，也不会被覆盖。
        """
        parts = key.split(PathSep.DOT)
        node = self._data

        # 逐层下沉，最后一层留给赋值
        for part in parts[:-1]:
            if part not in node:
                node[part] = {}
            node = node[part]
            # 中间层被别的类型占着（先 set("a", 1) 又 set("a.b", 2)）就明确报错，
            # 不然会静默把已有数据覆盖掉
            if not isinstance(node, dict):
                raise ContextError(f"路径中间层不是字典，无法写入: {key}")

        node[parts[-1]] = value

    def get(self, key: str) -> Any:
        """读取变量。自己层没有就往上问父级，都没有才抛 ContextError。"""
        try:
            return self._lookup(key)
        except ContextError:
            if self._parent is None:
                raise
            # 父级取不到时抛它自己的 ContextError —— 同一条链，类型天然一致
            return self._parent.get(key)

    def exists(self, key: str) -> bool:
        """变量在不在（自己层或父级）。给自己人做条件判断用。"""
        try:
            self.get(key)
        except ContextError:
            return False
        return True

    def _lookup(self, key: str) -> Any:
        """只查自己这一层。给 get 当「第一跳」，失败了好退回父级。"""
        node: Any = self._data
        for part in key.split(PathSep.DOT):
            if not isinstance(node, dict) or part not in node:
                raise ContextError(f"变量不存在: {key}")
            node = node[part]
        return node
