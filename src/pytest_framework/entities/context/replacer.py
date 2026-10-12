"""占位符解析：把 yaml 里的 ${...} 换成实际值。

只支持**一层**占位符（不支持 ${f(${g()})} 这种嵌套），遇到嵌套会明确报错 ——
不检测的话正则会只匹配里层、把外层留在字符串里，产出一个半解析的怪值，
排查起来很痛苦。

课程项目在这一步踩的坑，这里都绕开：
  - 用 str.index('$') 找第一个 $ → 数据里有孤立 $ 就错位（这里用正则）
  - 替换完 json.loads 还原 → 类型不稳（这里全程不碰 json）
  - 参数不 strip → ${f(a, b)} 第二个参数带空格（这里 strip）
"""

import re
from dataclasses import dataclass
from typing import Any

from pytest_framework.entities.constants.context import Placeholder
from pytest_framework.entities.context.context import Context
from pytest_framework.entities.context.functions import call
from pytest_framework.entities.contracts import CaseLike
from pytest_framework.entities.exception.errors import ContextError

# 抠出 ${...}：用 [^{}] 排除花括号，保证不会跨过 } 去乱吞
_PLACEHOLDER = re.compile(
    re.escape(Placeholder.OPEN) + r"([^{}]*)" + re.escape(Placeholder.CLOSE)
)

# 嵌套检测：${ 之后、下一个 } 之前又出现 ${
_NESTED = re.compile(
    re.escape(Placeholder.OPEN) + r"[^{}]*" + re.escape(Placeholder.OPEN)
)

# 有括号 = 函数调用（函数名 + 参数串）
_FUNC_CALL = re.compile(r"^([A-Za-z_]\w*)\((.*)\)$", re.S)


@dataclass
class ResolvedCase:
    """占位符已替换完的用例副本。

    为什么是副本、而不是就地改原 case：
      ExecuteCase 是 pytest 在**收集阶段**一次性构造的，整个 session 共用，
      --reruns 重跑拿到的还是同一个对象。就地替换会让第二遍跑到第一遍留下的脏数据。

    ⚠️ 字段与 framework/contracts.py 的 CaseLike、adapter 的 ExecuteCase 保持一致（三处同步改）。
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


def _resolve_one(expr: str, context: Context) -> Any:
    """解析单个 ${} 里的表达式：带括号当函数调，否则当变量引用。"""
    matched = _FUNC_CALL.match(expr.strip())

    if matched is None:
        # 没括号 → 变量引用，支持 a.b 点号路径
        return context.get(expr.strip())

    func_name, raw_args = matched.group(1), matched.group(2)
    args = (
        [arg.strip().strip("'\"") for arg in raw_args.split(",")]
        if raw_args.strip()
        else []
    )
    return call(func_name, *args)


def resolve_str(text: str, context: Context) -> Any:
    """解析字符串里的占位符。

    整串**恰好**是一个占位符时保留原类型（${count} 取到 int 就是 int）；
    混排在字符串里（如 "id-${n}"）则替换后按字符串拼接。
    """
    if Placeholder.OPEN not in text:
        return text

    if _NESTED.search(text):
        raise ContextError(f"不支持嵌套占位符: {text}")

    whole = _PLACEHOLDER.fullmatch(text)
    if whole:
        return _resolve_one(whole.group(1), context)

    return _PLACEHOLDER.sub(
        lambda m: str(_resolve_one(m.group(1), context)), text
    )


def resolve_value(value: Any, context: Context) -> Any:
    """递归解析容器里的占位符。只动 value 不动 key —— key 是结构，不是数据。"""
    if isinstance(value, str):
        return resolve_str(value, context)
    if isinstance(value, dict):
        return {k: resolve_value(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_value(v, context) for v in value]
    return value


def resolve_case(case: CaseLike, context: Context) -> ResolvedCase:
    """把「要发出去的东西」（url / headers / data）里的占位符解析成实际值。

    validations / extracts 是规则不是数据，原样带过去，不解析；
    db_validations **要**解析 —— 里面的 where 条件值常常是变量（如 ${user_id}）；
    path_params 也要解析 —— 它的值同样可能是变量（如 {accountNo} 填 ${account_no}）。
    """
    return ResolvedCase(
        api_name=case.api_name,
        url=resolve_str(case.url, context),
        method=case.method,
        headers=resolve_value(case.headers, context),
        case_name=case.case_name,
        data=resolve_value(case.data, context),
        validations=case.validations,
        extracts=case.extracts,
        db_validations=resolve_value(case.db_validations, context),
        path_params=resolve_value(case.path_params, context),
    )
