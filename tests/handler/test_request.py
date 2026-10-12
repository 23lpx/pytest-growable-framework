"""RequestHandler 的两件事：参数位置推断、路径参数拼装。

这个类只做「发请求」这一步的适配，不认识 yaml、不做断言 —— 所以测试也短。
"""

import pytest

from pytest_framework.adapters.execute_case import ExecuteCase
from pytest_framework.adapters.request import RequestHandler
from pytest_framework.entities.constants.http import Header, HttpParam
from pytest_framework.entities.exception.errors import RequestError


def _case(
    url: str = "/x",
    path_params: dict | None = None,
    method: str = "GET",
    headers: dict | None = None,
    data: dict | None = None,
) -> ExecuteCase:
    """造一条最小用例 —— 只填这个类用得上的字段。"""
    return ExecuteCase(
        api_name="测试接口",
        url=url,
        method=method,
        headers=headers or {},
        case_name="用例",
        data=data or {},
        validations=[],
        path_params=path_params or {},
    )


class TestBuildPath:
    """路径参数拼装：url 里的 {名字} 换成用例给的值。"""

    def test_没有占位符时原样返回(self) -> None:
        assert RequestHandler._build_path(_case("/a/b/c")) == "/a/b/c"

    def test_单个占位符(self) -> None:
        path = RequestHandler._build_path(
            _case("/api/group/v1/detail/{groupId}", {"groupId": 123})
        )
        assert path == "/api/group/v1/detail/123"

    def test_多个占位符(self) -> None:
        path = RequestHandler._build_path(
            _case("/api/{module}/v1/detail/{id}", {"module": "group", "id": 7})
        )
        assert path == "/api/group/v1/detail/7"

    def test_值做URL编码(self) -> None:
        """注入串这类值必须编码，否则会把路径结构冲掉（多出几个 / ）。"""
        path = RequestHandler._build_path(
            _case("/api/detail/{id}", {"id": "' OR '1'='1"})
        )
        assert path == "/api/detail/%27%20OR%20%271%27%3D%271"
        assert " " not in path

    def test_占位符没填全会报错(self) -> None:
        """漏填要在发出去之前就喊 —— 否则只会得到个看不懂的 404。"""
        with pytest.raises(RequestError, match="路径参数没填全"):
            RequestHandler._build_path(
                _case("/api/{module}/detail/{id}", {"module": "group"})
            )


class TestPickParamSlot:
    """参数位置推断：GET 走查询串，POST 按 Content-Type 决定 json 还是表单。"""

    def test_get走params(self) -> None:
        slot = RequestHandler._pick_param_slot(_case(method="GET", data={"p": 1}))
        assert slot == {HttpParam.PARAMS: {"p": 1}}

    def test_delete也走params(self) -> None:
        slot = RequestHandler._pick_param_slot(_case(method="DELETE", data={"p": 1}))
        assert slot == {HttpParam.PARAMS: {"p": 1}}

    def test_post加json头走json(self) -> None:
        slot = RequestHandler._pick_param_slot(
            _case(method="POST", headers={Header.CONTENT_TYPE: "application/json"}, data={"p": 1})
        )
        assert slot == {HttpParam.JSON: {"p": 1}}

    def test_post无json头走表单(self) -> None:
        slot = RequestHandler._pick_param_slot(
            _case(
                method="POST",
                headers={Header.CONTENT_TYPE: "application/x-www-form-urlencoded"},
                data={"p": 1},
            )
        )
        assert slot == {HttpParam.DATA: {"p": 1}}
