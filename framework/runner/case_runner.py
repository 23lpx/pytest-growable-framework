import logging

from framework.client.http_client import HttpClient
from framework.context.context import Context
from framework.context.replacer import resolve_case
from framework.contracts import CaseLike
from framework.exception.base import FrameworkError
from framework.handler.extract_handler import ExtractHandler
from framework.handler.request_handler import RequestHandler
from framework.handler.validation_handler import ValidationHandler

logger = logging.getLogger(__name__)


class CaseRunner:
    """执行「单条」用例：run() 只做编排，干活都在 handler 里。

    四步：解析占位符 -> 发送请求 -> 校验 -> 提取。

    为什么校验排在提取前面（fail-fast）：校验没过就不往变量池里写东西，
    免得「拿一条失败响应的 token 去跑后面的用例」，把失败的根因搅浑。

    不做 case 循环、不做测试发现、不管生命周期 —— 那些是 pytest 的活。
    HttpClient 和 Context 都由外面注入（不 new、不 close），生命周期归 fixture。

    异常：不吞。捕获到框架异常就补上 case_name 上下文、记日志，然后原样往上抛，
    由 pytest 决定测试失败。
    """

    def __init__(self, client: HttpClient, context: Context) -> None:
        self.context = context
        self.request_handler = RequestHandler(client)
        self.validation_handler = ValidationHandler()
        self.extract_handler = ExtractHandler()

    def run(self, case: CaseLike) -> None:
        try:
            # 1. 解析占位符 —— 产出**副本**，绝不就地改 case：
            #    case 是收集阶段构造的，整个 session 共用，--reruns 重跑还是它
            resolved = resolve_case(case, self.context)
            # 2. 发送请求
            resp = self.request_handler.send(resolved)
            # 3. 校验
            self.validation_handler.validate(resolved, resp)
            # 4. 提取，写进变量池供后续用例引用（用原 case：extracts 是规则，不含占位符）
            self.extract_handler.extract(case, resp, self.context)
        except FrameworkError as e:
            e.add_context(f"case_name={case.case_name}")
            # 用 exception 而不是 error —— 把栈一起留下。
            # 只有一行消息的话，跨多层调用时根本看不出是哪一层炸的。
            logger.exception(f"用例执行失败: {e}")
            raise
