import pytest

from framework.adapter.execute_case import ExecuteCase
from framework.model.case_model import CaseModel
from framework.runner.case_runner import CaseRunner


class TestLogin:

    @pytest.mark.parametrize(
        "case",
        [c.to_pytest_param() for c in ExecuteCase.from_model(CaseModel('/data/login_cases.yaml'))],
    )
    def test_login(self, case, base_url):
        CaseRunner(base_url).run(case)
