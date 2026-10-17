"""配置：把「在哪测」从「测什么」里分出来。

用例数据（yaml 的 `data`）描述「测什么」—— 换环境不该变；
配置描述「在哪测」—— 换环境就变，还可能带敏感值（密码 / 连接串）。

优先级：命令行 > 环境变量 > 配置文件。
命令行那一层在 `conftest` 里合 —— `Config` 不认识 pytest，也不该认识。

配置和变量池**都是** `${...}` 的取值来源，所以 `Config` 要能当 `Context` 的父级
（见 `contracts.VariableSource`）：`${login.username}` 走配置层、`${token}` 走变量层，
用例作者不用记两套语法。
"""

import os
from collections.abc import Mapping
from typing import Any, TypeVar

from pytest_framework.entities.constants.config import ConfigFile, EnvVar
from pytest_framework.entities.constants.context import PathSep
from pytest_framework.entities.context.context import Context
from pytest_framework.entities.exception.errors import ConfigError, YamlReadError
from pytest_framework.adapters.reader import YamlRead

_Num = TypeVar("_Num", int, float)


class Config:
    """一份配置，按点号路径取值（如 `login.username`）。

    内部就是一个 `Context` —— 「a.b.c 怎么取」的逻辑不写第二份。
    暴露的 `get` / `exists` 与 `Context` 语义一致（取不到抛 `ContextError`），
    所以它能直接当 `Context` 的 parent 用，穿透时不必做异常转换。
    """

    def __init__(self, raw: dict) -> None:
        self._ctx = Context()
        self._flatten(raw)

    @classmethod
    def load(
        cls,
        file_path: str = ConfigFile.DEFAULT_PATH,
        environ: Mapping[str, str] | None = None,
    ) -> "Config":
        """读配置文件，再叠一层环境变量覆盖。

        `environ` 默认取 `os.environ`；允许显式传是为了单测能注入，
        不必去打全局补丁（改 os.environ 的测试会互相污染）。
        """
        raw = cls._read(file_path)
        _overlay_env(raw, os.environ if environ is None else environ)
        return cls(raw)

    @staticmethod
    def _read(file_path: str) -> dict:
        if not YamlRead.exists(file_path):
            # 文件不存在 ≠ 配置错误：CI / 容器里本来就**不带** config.yaml（敏感值不入库），
            # 全靠 APP_* 环境变量注入。回落到 example 模板 —— **结构和类型**靠它：
            # timeout 必须是 int，而环境变量天生是字符串，没有原值就没法转出正确类型。
            # 真正的值由环境变量叠上去覆盖（占位值不会被用到，缺了会在 get 那步报错）。
            example = file_path.replace('.yaml', '.example.yaml')
            if YamlRead.exists(example):
                return YamlRead.read(example)
            return {}
        try:
            raw = YamlRead.read(file_path)
        except YamlReadError as e:
            # 文件在、但格式坏 / 编码错 —— 这是硬错误，不能静默吞掉
            raise ConfigError(f"配置加载失败: {file_path}") from e
        if not isinstance(raw, dict):
            raise ConfigError(f"配置根节点必须是字典: {file_path}")
        return raw

    def _flatten(self, raw: dict, prefix: str = "") -> None:
        """嵌套 dict 摊成点号路径。

        yaml 写成嵌套是给**人**看着舒服的（http: timeout: 10），
        取的时候统一走点号路径（http.timeout），和 Context 一套用法。
        """
        for key, value in raw.items():
            path = f"{prefix}{PathSep.DOT}{key}" if prefix else key
            if isinstance(value, dict):
                self._flatten(value, path)
            else:
                self._ctx.set(path, value)

    def get(self, key: str) -> Any:
        """按点号路径取值。取不到抛 `ContextError`（与 `Context` 同一套语义）。"""
        return self._ctx.get(key)

    def exists(self, key: str) -> bool:
        return self._ctx.exists(key)


def _overlay_env(raw: dict, environ: Mapping[str, str]) -> None:
    """把 `APP_` 前缀的环境变量叠到配置上（就地改 raw）。

    命名约定见 `EnvVar`。值的类型跟着配置里**原有值**走 —— 环境变量天生是
    字符串，不转的话 `timeout` 会变成 `"30"` 一路传进 requests。
    """
    for name, value in environ.items():
        if not name.startswith(EnvVar.PREFIX):
            continue

        parts = name[len(EnvVar.PREFIX):].lower().split(EnvVar.LEVEL)
        node = raw
        for part in parts[:-1]:
            child = node.get(part)
            if not isinstance(child, dict):
                child = {}
                node[part] = child
            node = child

        node[parts[-1]] = _cast(value, node.get(parts[-1]))


def _cast(value: str, current: Any) -> Any:
    """按原有值的类型转换环境变量。

    没有原值（环境变量新加的 key）就保持字符串 —— 无从判断该转成什么。
    只处理数字：bool 的写法太杂（true / yes / 1 / on），真需要时再加。
    （配置里若出现 bool，`int("true")` 会直接抛 ConfigError，不会静默出错。）
    """
    if isinstance(current, int):
        return _as_number(value, int)
    if isinstance(current, float):
        return _as_number(value, float)
    return value


def _as_number(value: str, kind: type[_Num]) -> _Num:
    try:
        return kind(value)
    except ValueError as e:
        raise ConfigError(f"配置值不是合法数字: {value}") from e
