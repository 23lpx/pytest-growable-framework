import logging

from pytest_framework.adapters.execute_case import ExecuteCase
from pytest_framework.entities.context.context import Context
from pytest_framework.entities.exception.base import FrameworkError
from pytest_framework.entities.model.scenario_model import ScenarioModel
from pytest_framework.infrastructure import report
from pytest_framework.ports.sender import Sender
from pytest_framework.usecases.case_runner import CaseRunner

logger = logging.getLogger(__name__)


class ScenarioRunner:
    """执行一个业务场景：按数据里的顺序，逐步把用例交给 CaseRunner。

    它只管两件事 —— 这两件事恰好是 CaseRunner 不管的：
      1. **顺序**：遍历 scenario.steps，顺序由 yaml 决定，pytest 不参与
      2. **步骤边界**：日志和报告**都**标出「第 N/M 步」，失败时把步骤信息补进上下文

    不重写执行逻辑：每条 case 仍走 CaseRunner 的四步（解析→发送→校验→提取）。
    CaseRunner 也不知道自己是被谁调的 —— 它只认一条 case。这就是「两个循环器
    共用一个执行器」：循环策略归调用方，CaseRunner 只管跑好这一条。

    注意：场景模式**不需要** login fixture —— 顺序天然成立，
    「前置」就是第一步（登录步），拿到的 token 直接进变量池供后面几步引用。
    """

    def __init__(self, client: Sender, context: Context) -> None:
        self.case_runner = CaseRunner(client, context)

    def run(self, scenario: ScenarioModel) -> None:
        total = len(scenario.steps)
        logger.info("=== 场景开始: %s（共 %d 步）===", scenario.name, total)

        for index, step in enumerate(scenario.steps, start=1):
            api_name = step.api.api_name
            label = f"步骤 {index}/{total}: {api_name}"
            logger.info("--- %s ---", label)
            try:
                # 日志给**跑的人**看（控制台 / app.log），step 给**看报告的人**看
                # —— 同一份顺序信息，两个出口。
                with report.step(label):
                    for case in ExecuteCase.from_model(step):
                        self.case_runner.run(case)
            except FrameworkError as e:
                # CaseRunner 已经补了 case_name；这里补上「第几步」——
                # 没有这层上下文，报告里只看到一个 FAILED，不知道断在哪一步。
                e.add_context(f"场景={scenario.name} 步骤={index}/{total} {api_name}")
                raise

        logger.info("=== 场景结束: %s ===", scenario.name)
