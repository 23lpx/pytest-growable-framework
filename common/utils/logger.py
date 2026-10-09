import logging
import os
import logging_tree
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from common.utils.path import _project_root

def init_logger():
    os.makedirs(str(_project_root())+'/logs',exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter('%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(funcName)s - %(message)s')
    #控制台控制器
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    #文件
    # fh = RotatingFileHandler(
    #     str(_project_root())+'/logs/test.log',maxBytes=1024*1024*5,backupCount=5,encoding='utf-8'
    # )
    # fh.setLevel(logging.DEBUG)
    # fh.setFormatter(fmt)
    # logger.addHandler(fh)

    #按日期切
    handler = TimedRotatingFileHandler(
        str(_project_root())+"/logs/app.log",
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

# if __name__ == '__main__':
#     init_logger()
#     logging_tree.printout()
#     logger_test = logging.getLogger(__name__)
#     logger_test.debug('debug')
#     logger_test.info('info')
#     logger_test.warning('warning')
#     logger_test.error('error')

