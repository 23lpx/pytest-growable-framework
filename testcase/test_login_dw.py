import pytest

from framework.adapter.execute_case import ExecuteCase
from framework.model.case_model import CaseModel
from framework.runner.case_runner import CaseRunner


class TestLoginDw:
    """电网系统登录（POST + json body）。"""

    @pytest.mark.parametrize(
        "case",
        [c.to_pytest_param() for c in ExecuteCase.from_model(CaseModel('/data/login_dw_cases.yaml'))],
    )
    def test_login_dw(self, case, client, context):
        CaseRunner(client, context).run(case)
