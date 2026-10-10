from framework.exception.base import FrameworkError


class ConfigError(FrameworkError):
    """配置错误。"""


class DataError(FrameworkError):
    """数据层错误的父类（读取 / 解析）。"""


class YamlReadError(DataError):
    """yaml 读取失败：文件不存在 / 格式错误 / 编码错误。来自 Reader。"""


class CaseParseError(DataError):
    """用例数据结构不符合规范：必要字段缺失 / 结构错误。来自 Model 解析。"""


class ModelError(FrameworkError):
    """模型层错误。"""


class ContextError(FrameworkError):
    """变量池相关错误：变量不存在 / 路径中间层类型不对 / 占位符语法问题。

    来自 Context（含 replacer）。和 ExtractError 分开，是因为根因不同 ——
    一个是「响应里取不到」，一个是「池子里没有这个 key」，混用会让排错变糊。
    """


class RequestError(FrameworkError):
    """HTTP 请求失败：网络错误 / 超时 / 请求异常。来自 Client。"""


class ExtractError(FrameworkError):
    """响应数据提取失败。来自 Extract Handler。"""


class ValidationError(FrameworkError):
    """响应校验失败。来自 Validation Handler。"""
