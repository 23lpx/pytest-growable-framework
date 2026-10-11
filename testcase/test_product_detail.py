import pytest

from framework.adapter.execute_case import ExecuteCase
from framework.model.case_model import CaseModel
from framework.runner.case_runner import CaseRunner


class TestProductDetail:
    """商品详情（POST + json body）。"""

    @pytest.mark.parametrize(
        "case",
        [c.to_pytest_param() for c in ExecuteCase.from_model(CaseModel('/data/product_detail_cases.yaml'))],
    )
    def test_product_detail(self, case, client, context):
        CaseRunner(client, context).run(case)
