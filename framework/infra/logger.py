import logging
import os
from logging.handlers import TimedRotatingFileHandler

from framework.constants.logging import LogConfig
from framework.infra.masking import MaskingFormatter, install_masking
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

    # 从源头打码：record 一创建就换掉敏感字段，之后所有出口
    # （我们的控制台/文件、pytest 的「Captured log」）拿到的都是打码数据。
    install_masking()

    # 注意**不能设 propagate = False** —— 那会让日志冒不到 root，而 pytest 的
    # 日志捕获正是挂在 root 上：一旦断开，用例失败时报告里一条日志都看不到，
    # 控制台又被 stderr 捕获吞掉，等于瞎了。

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
