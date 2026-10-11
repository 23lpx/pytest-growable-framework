import logging

from framework.adapter.execute_case import ExecuteCase
from framework.client.http_client import HttpClient
from framework.context.context import Context
from framework.exception.base import FrameworkError
from framework.model.scenario_model import ScenarioModel
from framework.runner.case_runner import CaseRunner

logger = logging.getLogger(__name__)


class ScenarioRunner:
    """执行一个业务场景：按数据里的顺序，逐步把用例交给 CaseRunner。

    它只管两件事 —— 这两件事恰好是 CaseRunner 不管的：
      1. **顺序**：遍历 scenario.steps，顺序由 yaml 决定，pytest 不参与
      2. **步骤边界**：日志标出「第 N/M 步」，失败时把步骤信息补进上下文

    不重写执行逻辑：每条 case 仍走 CaseRunner 的四步（解析→发送→校验→提取）。
    CaseRunner 也不知道自己是被谁调的 —— 它只认一条 case。这就是「两个循环器
    共用一个执行器」：循环策略归调用方，CaseRunner 只管跑好这一条。

    注意：场景模式**不需要** login fixture —— 顺序天然成立，
    「前置」就是第一步（登录步），拿到的 token 直接进变量池供后面几步引用。
    """

    def __init__(self, client: HttpClient, context: Context) -> None:
        self.case_runner = CaseRunner(client, context)

    def run(self, scenario: ScenarioModel) -> None:
        total = len(scenario.steps)
        logger.info("=== 场景开始: %s（共 %d 步）===", scenario.name, total)

        for index, step in enumerate(scenario.steps, start=1):
            api_name = step.api.api_name
            logger.info("--- 步骤 %d/%d: %s ---", index, total, api_name)
            try:
                for case in ExecuteCase.from_model(step):
                    self.case_runner.run(case)
            except FrameworkError as e:
                # CaseRunner 已经补了 case_name；这里补上「第几步」——
                # 没有这层上下文，报告里只看到一个 FAILED，不知道断在哪一步。
                e.add_context(f"场景={scenario.name} 步骤={index}/{total} {api_name}")
                raise

        logger.info("=== 场景结束: %s ===", scenario.name)
