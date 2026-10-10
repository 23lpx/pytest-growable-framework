import pytest

from framework.adapter.execute_case import ExecuteCase
from framework.model.case_model import CaseModel
from framework.runner.case_runner import CaseRunner


class TestUser:
    """新增用户接口。

    参数里的 login 是**故意的**：它保证前置登录已跑过、token 进了变量池，
    yaml 里的 ${token} 才取得到值。这是跨用例关联的标准做法 ——
    用 fixture 表达前置依赖，而不是指望用例执行顺序。
    """

    @pytest.mark.parametrize(
        "case",
        [c.to_pytest_param() for c in ExecuteCase.from_model(CaseModel('/data/add_user_cases.yaml'))],
    )
    def test_add_user(self, case, client, context, login):
        CaseRunner(client, context).run(case)
