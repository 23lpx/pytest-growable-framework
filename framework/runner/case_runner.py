import logging

from framework.contracts import CaseLike
from framework.exception.base import FrameworkError
from framework.handler.request_handler import RequestHandler
from framework.handler.validation_handler import ValidationHandler

logger = logging.getLogger(__name__)


class CaseRunner:
    """执行「单条」用例：run() 只做编排，干活都在 handler 里。

    三步：发送请求 -> 校验（提取待 Context 设计好后接进来）。
    不做 case 循环、不做测试发现、不管生命周期 —— 那些是 pytest 的活。

    异常：不吞。捕获到框架异常就补上 case_name 上下文、记日志，然后原样往上抛，
    由 pytest 决定测试失败。
    """

    def __init__(self, base_url: str) -> None:
        self.request_handler = RequestHandler(base_url)
        self.validation_handler = ValidationHandler()

    def run(self, case: CaseLike) -> None:
        try:
            # 1. 发送请求
            resp = self.request_handler.send(case)
            # 2. 校验
            self.validation_handler.validate(case, resp)
            # 3. 提取 —— 等 Context 那步再做
        except FrameworkError as e:
            e.add_context(f"case_name={case.case_name}")
            logger.error(f"用例执行失败: {e}")
            raise
