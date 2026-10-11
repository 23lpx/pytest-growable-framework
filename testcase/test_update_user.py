import pytest

from framework.adapter.execute_case import ExecuteCase
from framework.model.case_model import CaseModel
from framework.runner.case_runner import CaseRunner


class TestUpdateUser:
    """修改用户接口（纯表单，不依赖 token，所以**不需要** login fixture）。"""

    @pytest.mark.parametrize(
        "case",
        [c.to_pytest_param() for c in ExecuteCase.from_model(CaseModel('/data/update_user_cases.yaml'))],
    )
    def test_update_user(self, case, client, context):
        CaseRunner(client, context).run(case)
