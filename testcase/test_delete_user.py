import pytest

from framework.adapter.execute_case import ExecuteCase
from framework.model.case_model import CaseModel
from framework.runner.case_runner import CaseRunner


class TestDeleteUser:
    """删除用户接口（只看 user_id，不依赖 token）。"""

    @pytest.mark.parametrize(
        "case",
        [c.to_pytest_param() for c in ExecuteCase.from_model(CaseModel('/data/delete_user_cases.yaml'))],
    )
    def test_delete_user(self, case, client, context):
        CaseRunner(client, context).run(case)
