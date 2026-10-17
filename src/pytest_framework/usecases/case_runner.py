import logging

from pytest_framework.adapters.db_checker import DbChecker
from pytest_framework.adapters.request import RequestHandler
from pytest_framework.entities.context.context import Context
from pytest_framework.entities.context.replacer import ResolvedCase, resolve_case
from pytest_framework.entities.contracts import CaseLike
from pytest_framework.entities.exception.base import FrameworkError
from pytest_framework.entities.exception.errors import DatabaseError
from pytest_framework.ports.sender import Sender
from pytest_framework.usecases.extract import ExtractHandler
from pytest_framework.usecases.validation import ValidationHandler

logger = logging.getLogger(__name__)


class CaseRunner:
    """执行「单条」用例：run() 只做编排，干活都在 handler 里。

    五步：解析占位符 -> 发送请求 -> 校验响应 -> 校验库 -> 提取。

    为什么校验排在提取前面（fail-fast）：校验没过就不往变量池里写东西，
    免得「拿一条失败响应的 token 去跑后面的用例」，把失败的根因搅浑。
    查库排在提取前面是同一个道理。

    不做 case 循环、不做测试发现、不管生命周期 —— 那些是 pytest 的活。
    `client`（满足 Sender 端口，不一定是 HttpClient）、`Context`、`db_checker`
    都由外面注入（不 new、不 close），生命周期归 fixture。

    `db_checker` 可以是 None：没配数据库时纯接口用例照样跑，只有**声明了 db 断言**
    的用例才会撞上「没注入」这个错 —— 让绝大多数用例免受数据库可用性的牵连。

    异常：不吞。捕获到框架异常就补上 case_name 上下文、记日志，然后原样往上抛，
    由 pytest 决定测试失败。
    """

    def __init__(
        self,
        client: Sender,
        context: Context,
        db_checker: DbChecker | None = None,
    ) -> None:
        self.context = context
        self.request_handler = RequestHandler(client)
        self.validation_handler = ValidationHandler()
        self.db_checker = db_checker
        self.extract_handler = ExtractHandler()

    def run(self, case: CaseLike) -> None:
        try:
            # 1. 解析占位符 —— 产出**副本**，绝不就地改 case：
            #    case 是收集阶段构造的，整个 session 共用，--reruns 重跑还是它
            resolved = resolve_case(case, self.context)
            # 2. 发送请求
            resp = self.request_handler.send(resolved)
            # 3. 校验响应
            self.validation_handler.validate(resolved, resp)
            # 4. 校验库 —— 「接口说自己成功了」之外，再问一句「库里真是这样吗」
            self._check_db(resolved)
            # 5. 提取，写进变量池供后续用例引用（用原 case：extracts 是规则，不含占位符）
            self.extract_handler.extract(case, resp, self.context)
        except FrameworkError as e:
            e.add_context(f"case_name={case.case_name}")
            # 用 exception 而不是 error —— 把栈一起留下。
            # 只有一行消息的话，跨多层调用时根本看不出是哪一层炸的。
            logger.exception(f"用例执行失败: {e}")
            raise

    def _check_db(self, resolved: ResolvedCase) -> None:
        """第 4 步。没写 db 段直接跳过；写了却没注入 checker 是**配置问题**，当场喊，
        别让它伪装成「用例通过」。"""
        if not resolved.db_validations:
            return

        if self.db_checker is None:
            raise DatabaseError(
                "用例声明了 db 断言，但没有可用的数据库连接"
                "（检查 config/config.yaml 里的 db 段）"
            )
        self.db_checker.check(resolved.db_validations)
