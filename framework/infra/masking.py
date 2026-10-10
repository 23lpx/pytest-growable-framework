"""日志脱敏：日志落地前把敏感值打码。

为什么用自定义 Formatter，而不是 Filter / 调用点手打：

- 调用点手打：漏一处就泄漏，而且管不到 logger.exception 输出里的异常栈；
- logging.Filter：作用在 record 上、早于格式化，改结构化 args 得自己深拷贝，
  对栈文本也无能为力；
- 自定义 Formatter：所有 handler 挂同一个就全覆盖（包括将来的 allure handler），
  既能按 key 精确打码结构化 args，又能对最终文本做正则兜底。
"""

import copy
import logging
import re
from typing import Any

from framework.constants.logging import MaskConfig

# 长 key 排前面，避免 access_token 被 token 抢先匹配掉
_KEYS = "|".join(sorted(MaskConfig.SENSITIVE_KEYS, key=len, reverse=True))

# 兜底用：匹配 passwd=xxx / 'token': 'xxx' 这类已渲染成文本的明文
_TEXT_PATTERN = re.compile(
    rf"(?i)({_KEYS})(['\"]?\s*[:=]\s*['\"]?)([^\s,'\"}}\]]+)"
)


def _is_sensitive(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    return any(k in lowered for k in MaskConfig.SENSITIVE_KEYS)


def mask(value: Any) -> Any:
    """递归给 dict / list 里的敏感字段打码，返回新对象。

    一律产出副本：脱敏是「日志表现层」的事，绝不能碰到真正发出去的数据。
    命中时**保留 key 只换值** —— 删掉 key 反而丢掉「这里本来有值」的信息。
    """
    if isinstance(value, dict):
        return {
            k: MaskConfig.MASK if _is_sensitive(k) else mask(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(mask(v) for v in value)
    return value


def mask_text(text: str) -> str:
    """对已渲染的文本做正则兜底，覆盖 f-string 消息和异常栈里的明文。"""
    return _TEXT_PATTERN.sub(rf"\1\2{MaskConfig.MASK}", text)


class MaskingFormatter(logging.Formatter):
    """先按 key 打码结构化 args，再对最终文本兜底。

    按 key 打码要求日志写成 %s 风格（logger.debug("请求参数: %s", data)）——
    用 f-string 预渲染成字符串就只剩正则兜底这一条路了。
    """

    def format(self, record: logging.LogRecord) -> str:
        # 只在副本上动手：原 record 可能还要被别的 handler 用
        copy_record = copy.copy(record)
        if isinstance(copy_record.args, dict):
            copy_record.args = mask(copy_record.args)
        elif isinstance(copy_record.args, tuple):
            copy_record.args = tuple(mask(arg) for arg in copy_record.args)

        return mask_text(super().format(copy_record))
