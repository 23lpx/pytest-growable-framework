import allure
import pytest

from pytest_framework.adapters.execute_case import ExecuteCase
from pytest_framework.infrastructure.http import HttpClient
from pytest_framework.entities.context.context import Context
from pytest_framework.usecases.case_runner import CaseRunner


def _params() -> list:
    """把用例转成 pytest 参数；yaml 里的元信息（xfail / smoke）在这一步翻成标记。

    为什么要「翻译」：yaml 驱动的用例**没有 Python 函数可以挂装饰器** ——
    标记写不进 yaml，只能在这层把 yaml 字段映射成 `pytest.mark.*`。

    `strict=True` 是有意的：这条是「已知缺陷、判据正确」，所以**红了算预期**；
    可一旦哪天被测系统把它修好了，用例会变绿 → pytest 报 **XPASS 失败** →
    提醒你回来把 yaml 里的 xfail 摘掉。**不摘就红**，缺陷不会悄悄溜走。
    """
    params = []
    for case in ExecuteCase.discover("data/api_shortlink"):
        marks = []
        if case.xfail:
            marks.append(pytest.mark.xfail(reason=case.xfail, strict=True))
        if case.smoke:
            marks.append(pytest.mark.smoke)
        if case.skip:
            marks.append(pytest.mark.skip(reason=case.skip))
        params.append(
            pytest.param(case, marks=marks, id=f"{case.api_name}:{case.case_name}")
        )
    return params


@allure.feature("短链平台")
class TestShortLink:
    """商用短链平台的**单接口**用例 —— 扫 `data/api_shortlink/`。

    挂的三样：
      · `shortlink_client`   —— base_url 指向短链平台（经网关）
      · `shortlink_login`    —— 登录一次拿 token 写进变量池
      · `shortlink_prepare`  —— 造**只读**的公共前置（专用分组 + 官方域名）
      · `cleanup_test_data`  —— 跑完把本次造的数据删掉（快照差集），让用例集**可反复运行**

    ⚠️ **这里的用例必须互相独立**：不许有「A 跑完把状态改了、B 才成立」的依赖。
       有前后关系的流程（删了再删、建了再查）一律走**场景**（`data/scenarios/`）。
       公共前置 `${g1_id}` 是**只读**的，谁也不许删它、改它。
    """

    @pytest.mark.parametrize("case", _params())
    def test_shortlink(
        self,
        case: ExecuteCase,
        shortlink_client: HttpClient,
        context: Context,
        shortlink_login,
        shortlink_prepare,
        cleanup_test_data,
    ) -> None:
        allure.dynamic.story(case.api_name)
        CaseRunner(shortlink_client, context).run(case)

