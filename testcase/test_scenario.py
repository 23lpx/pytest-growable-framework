import allure
import pytest

from framework.client.http_client import HttpClient
from framework.context.context import Context
from framework.model.scenario_model import ScenarioModel
from framework.runner.scenario_runner import ScenarioRunner


@allure.feature("业务场景")
class TestScenario:
    """所有业务场景：**一个 yaml 文件 = 一个 pytest 节点**。

    加场景 = 往 data/scenarios/ 丢一个 yaml，**不用写新的测试函数** ——
    这就是「一个执行框架，多份测试数据」在场景层的落地。

    注意「一个场景 = 一个节点」没变：这里只是把「有哪些场景」也从代码里挪出去了。
    每个场景内部仍然是顺序执行、步骤间靠变量池传值。
    """

    @pytest.mark.parametrize("scenario", ScenarioModel.discover(), ids=lambda s: s.name)
    def test_scenario(self, scenario: ScenarioModel, client: HttpClient, context: Context) -> None:
        allure.dynamic.story(scenario.name)
        ScenarioRunner(client, context).run(scenario)
