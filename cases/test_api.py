import allure
import pytest

from pytest_framework.adapters.db_checker import DbChecker
from pytest_framework.adapters.execute_case import ExecuteCase
from pytest_framework.infrastructure.http import HttpClient
from pytest_framework.entities.context.context import Context
from pytest_framework.usecases.case_runner import CaseRunner


@allure.feature("单接口")
class TestApi:
    """所有单接口用例：**一条 case = 一个 pytest 节点**（粒度没变）。

    加接口 = 往 `data/api/` 丢一个 yaml，**不用写新的测试函数**。
    这是数据驱动的主力 —— 单接口用例量大、彼此独立，最适合数据驱动。

    粒度：这里把每个接口文件里的用例**展平**再参数化，所以 `-k` / `-m` / 单条重跑
    仍然是单条粒度的（单接口就该这样）。用例 id 用 `接口名:用例名` ——
    光用 `case_name` 不唯一（"缺少必填参数"这种会跨接口重名）。

    `login` fixture 是**故意全挂**的：addUser 这类接口要 token，而它 session 级
    只登一次、零成本。统一成一个函数后没法再按文件声明，索性都挂上。
    """

    @pytest.mark.parametrize(
        "case",
        ExecuteCase.discover(),
        ids=lambda c: f"{c.api_name}:{c.case_name}",
    )
    def test_api(
        self,
        case: ExecuteCase,
        client: HttpClient,
        context: Context,
        db_checker: DbChecker | None,
        login,
    ) -> None:
        # 报告里按「接口」分组 —— 参数化 id 里虽然带着接口名，但那是字符串，分不了组
        allure.dynamic.story(case.api_name)
        CaseRunner(client, context, db_checker).run(case)
