import logging


class LogConfig:
    """日志配置常量 —— 魔法值收口在这里，调日志只改这个文件。"""

    # 日志挂在命名 logger 上，不挂 root（root 会把三方库日志一起兜进来）。
    # ⚠️ 必须**和包名一致**：各模块用 logging.getLogger(__name__)，名字是
    # "pytest_framework.xxx"，冒泡只会到 "pytest_framework" 就停。写成别的
    # （比如重构前的 "framework"）就一条都接不到 —— handler 形同虚设。
    LOGGER_NAME = "pytest_framework"

    # 格式里带 文件:行号 + 函数名 —— 一条日志直接指到代码位置，不用靠消息内容猜
    FORMAT = "%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(funcName)s - %(message)s"

    # 分层：文件留全量（排查用），控制台只留结论（不刷屏）
    FILE_LEVEL = logging.DEBUG
    CONSOLE_LEVEL = logging.INFO

    LOG_DIR = "logs"
    LOG_FILE = "app.log"


class MaskConfig:
    """脱敏配置。命中名单的字段在**进日志前**被打码，原始数据不动。"""

    # 子串匹配（大小写不敏感），所以 access_token / phoneNumber 这类也会命中
    SENSITIVE_KEYS = (
        "passwd",
        "password",
        "pwd",
        "token",
        "access_token",
        "authorization",
        "cookie",
        "id_card",
        "phone",
        "mobile",
    )

    MASK = "***"
