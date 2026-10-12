from pytest_framework.entities.exception.base import FrameworkError


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
    """校验失败：响应没达预期，或库里查到的和期望对不上。

    来自 Validation Handler / DbChecker。两者共用一个异常，是因为对使用者来说
    是同一件事（「断言没通过」），上层处理方式也一样。
    """


class DatabaseError(FrameworkError):
    """数据库本身出问题：连不上 / SQL 语法错 / 表名列名非法。

    来自 DB 底座与 DbChecker（生成 SQL 那一步）。

    ⚠️ 和 ValidationError 的分工要守住：**「查不动库」是 DatabaseError，
    「查到了但对不上」才是 ValidationError**。一个是环境坏了（配置错、服务没起），
    一个是用例失败（断言写了但功能有问题）。混在一起，排错时就会盯着断言看，
    而真正的问题在连接配置里。
    """
