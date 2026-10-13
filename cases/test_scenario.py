import allure
import pytest

from pytest_framework.entities.context.context import Context
from pytest_framework.entities.model.scenario_model import ScenarioModel
from pytest_framework.infrastructure.http import HttpClient
from pytest_framework.usecases.scenario_runner import ScenarioRunner


@allure.feature("短链平台")
class TestScenario:
    """短链平台的**业务场景**用例 —— 顺序由 yaml 列表决定，一个场景一个节点。

    **和单接口（`test_shortlink.py`）的分工**：
      · 单接口 —— 一条用例一个节点，**互相独立**；量大，能 `-k` / `-m` / 单条重跑；
      · 场景   —— 一个场景一个节点，**步骤有先后**；把「建了再删」「重名判重」
        这类天然有序的流程收在一起。

    ⚠️ **为什么不挂 `shortlink_prepare`**：场景的"前置"就是它的第一步（自己建），
       顺序天然成立，不需要外部造数。挂上反而会让场景意外依赖一个它没打算要的组。

    ⚠️ **场景也挂 `cleanup_test_data`**：多数场景末尾自己把数据删了，但万一中途某步
       失败、后面的清理步骤没跑到，残留就归兜底的快照差集处理。
    """

    @pytest.mark.parametrize(
        "scenario", ScenarioModel.discover(), ids=lambda s: s.name
    )
    def test_scenario(
        self,
        scenario: ScenarioModel,
        shortlink_client: HttpClient,
        context: Context,
        shortlink_login,
        cleanup_test_data,
    ) -> None:
        allure.dynamic.story(scenario.name)
        ScenarioRunner(shortlink_client, context).run(scenario)
