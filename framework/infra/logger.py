import logging
import os
from logging.handlers import TimedRotatingFileHandler

from framework.infra.path import _project_root


def init_logger() -> None:
    os.makedirs(str(_project_root()) + '/logs', exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter('%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(funcName)s - %(message)s')
    # 控制台控制器
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # 按日期切
    handler = TimedRotatingFileHandler(
        str(_project_root()) + "/logs/app.log",
        when="midnight",   # 午夜切
        interval=1,        # 每1天
        backupCount=7,     # 保留7份
        encoding="utf-8"
    )
    handler.suffix = "%Y-%m-%d"  # 切出来的文件名带日期

    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s - %(message)s"
    ))
    logger.addHandler(handler)
