import pytest

from framework.adapter.execute_case import ExecuteCase
from framework.model.case_model import CaseModel
from framework.runner.case_runner import CaseRunner


class TestGoodsList:
    """商品列表（GET + 查询串 params）。"""

    @pytest.mark.parametrize(
        "case",
        [c.to_pytest_param() for c in ExecuteCase.from_model(CaseModel('/data/goods_list_cases.yaml'))],
    )
    def test_goods_list(self, case, client, context):
        CaseRunner(client, context).run(case)
