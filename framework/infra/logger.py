import logging
import os
from logging.handlers import TimedRotatingFileHandler

from framework.constants.logging import LogConfig
from framework.infra.masking import MaskingFormatter
from framework.infra.path import _project_root


def init_logger() -> None:
    """初始化框架日志。

    幂等：重复调用不会重复挂 handler（重复挂会一条日志打两遍）。
    只配置一次即可，所以放在 conftest 顶部调用。

    挂在命名 logger "framework" 上，**不挂 root** —— root 会把 requests /
    urllib3 这些三方库的日志一并兜进来。框架内各模块用
    logging.getLogger(__name__)，名字形如 "framework.client.http_client"，
    会自然冒泡到这里。
    """
    logger = logging.getLogger(LogConfig.LOGGER_NAME)
    if logger.handlers:
        return

    # logger 本身放到最低，具体过滤交给各 handler 的 level
    logger.setLevel(logging.DEBUG)
    # 不再往上冒泡到 root —— root 那边可能有别家（如 pytest）的 handler，
    # 冒上去会重复输出
    logger.propagate = False

    # 两个 handler 共用同一个脱敏 formatter，保证哪一路输出都打码
    formatter = MaskingFormatter(LogConfig.FORMAT)

    console = logging.StreamHandler()
    console.setLevel(LogConfig.CONSOLE_LEVEL)
    console.setFormatter(formatter)
    logger.addHandler(console)

    log_dir = _project_root() / LogConfig.LOG_DIR
    os.makedirs(str(log_dir), exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        str(log_dir / LogConfig.LOG_FILE),
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"  # 切出来的文件名带日期
    file_handler.setLevel(LogConfig.FILE_LEVEL)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
