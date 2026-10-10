"""函数市场：yaml 里用 ${函数名(参数)} 调用的那些动态值。

这里是框架的**扩展点** —— 加函数 = 写个函数 + 挂 @register，
框架别处一行不用改。课程项目那套值钱的就是这个思路。
"""

import time
from datetime import date
from typing import Any, Callable

from framework.exception.errors import ContextError

FUNCTIONS: dict[str, Callable[..., Any]] = {}


def register(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """把函数登记进市场，yaml 里就能用 ${name(...)} 调它。"""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        FUNCTIONS[name] = func
        return func

    return decorator


def call(name: str, *args: Any) -> Any:
    """按名字调用已注册的函数。没注册过就抛错 —— 不静默返回空值。"""
    func = FUNCTIONS.get(name)
    if func is None:
        raise ContextError(f"未注册的函数: {name}()，已注册: {sorted(FUNCTIONS)}")

    try:
        return func(*args)
    except Exception as e:
        # 转成本层异常并保留原始错误（不吞）
        raise ContextError(f"函数 {name}() 执行失败") from e


@register("today")
def today() -> str:
    """今天的日期，如 2026-10-10。"""
    return date.today().isoformat()


@register("timestamp")
def timestamp() -> int:
    """当前时间戳（10 位，秒）。"""
    return int(time.time())
