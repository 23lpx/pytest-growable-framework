import allure
import pytest

from pytest_framework.adapters.execute_case import ExecuteCase
from pytest_framework.infrastructure.http import HttpClient
from pytest_framework.entities.context.context import Context
from pytest_framework.usecases.case_runner import CaseRunner


@allure.feature("短链平台")
class TestShortLink:
    """商用短链平台的单接口用例 —— **框架的第二个被测系统**。

    和 `cases/test_api.py` 的区别就三处，都在下面写着：
      · 扫的目录不同：`data/api_shortlink/`（不是 `data/api/`）
      · 用的客户端不同：`shortlink_client`（base_url 指向短链平台）
      · 挂的前置不同：`shortlink_login`（短链平台的登录，不是 flaskServer 的）

    **为什么不是加一个 `if` 判断扫哪个目录**：两个被测系统是并列的，不是分支。
    各自一个测试文件 = 各自一个入口 = 谁挂了不影响谁（flaskServer 没开的时候，
    短链平台的用例照样能跑）。
    """

    @pytest.mark.parametrize(
        "case",
        ExecuteCase.discover("data/api_shortlink"),
        ids=lambda c: f"{c.api_name}:{c.case_name}",
    )
    def test_shortlink(
        self,
        case: ExecuteCase,
        shortlink_client: HttpClient,
        context: Context,
        shortlink_login,
    ) -> None:
        allure.dynamic.story(case.api_name)
        CaseRunner(shortlink_client, context).run(case)
