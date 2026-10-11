from framework.client.http_client import HttpClient
from framework.context.context import Context
from framework.model.scenario_model import ScenarioModel
from framework.runner.scenario_runner import ScenarioRunner


class TestEcommerceFlow:
    """电商下单全链路（业务场景）。

    整个场景 = **一个 pytest 节点**：顺序由 yaml 决定，步骤间靠变量池传递。

    所以这里**不需要 login fixture** —— 那是单接口模式下为了凑前置才要的；
    场景模式下顺序天然成立，第一步就是登录。
    """

    def test_ecommerce_flow(self, client: HttpClient, context: Context) -> None:
        ScenarioRunner(client, context).run(ScenarioModel('/data/scenarios/ecommerce_flow.yaml'))
