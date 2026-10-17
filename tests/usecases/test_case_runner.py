"""CaseRunner 的编排测试 —— **全程不碰网络**。

怎么做到不碰网络：注入一个假 Sender。
这本身就是「依赖倒置」的验证 —— CaseRunner 只认 `contracts.Sender` 端口，
压根不知道 `client.HttpClient` 存在（它也没 import 过）。
"""

from typing import Any

import pytest

from pytest_framework.adapters.execute_case import ExecuteCase
from pytest_framework.entities.context.context import Context
from pytest_framework.entities.exception.errors import ValidationError
from pytest_framework.usecases.case_runner import CaseRunner


class FakeSender:
    """假发送器：只实现 Sender 契约的 `request()`，把给定响应原样返回。

    顺便记下每次调用，好断言「实际发出去的是什么」。
    """

    def __init__(self, response: Any) -> None:
        self._response = response
        self.calls: list[dict] = []

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        self.calls.append({"method": method, "path": path, **kwargs})
        return self._response


def make_case(**overrides: Any) -> ExecuteCase:
    """一条最小可执行用例，字段按需覆盖。"""
    base = {
        "api_name": "用户登录",
        "url": "/dar/user/login",
        "method": "POST",
        "headers": {"Content-Type": "application/x-www-form-urlencoded"},
        "case_name": "正常登录",
        "data": {"user_name": "u", "passwd": "p"},
        "validations": [],
        "extracts": {},
    }
    base.update(overrides)
    return ExecuteCase(**base)


class TestCaseRunner:

    def test_runs_all_four_steps(self, make_response) -> None:
        """解析 → 发送 → 校验 → 提取，一条龙；提取的值进了变量池。"""
        sender = FakeSender(make_response({"msg": "登录成功", "token": "jwt-abc"}))
        ctx = Context()
        case = make_case(
            validations=[{"contains": {"msg": "登录成功"}}],
            extracts={"token": "$.token"},
        )

        CaseRunner(sender, ctx).run(case)

        assert len(sender.calls) == 1
        assert sender.calls[0]["method"] == "POST"
        assert sender.calls[0]["path"] == "/dar/user/login"
        assert ctx.get("token") == "jwt-abc"

    def test_placeholder_resolved_before_send(self, make_response) -> None:
        """前置用例提取的 ${token} 在发送前就被解析掉了。"""
        sender = FakeSender(make_response({"msg": "ok"}))
        ctx = Context()
        ctx.set("token", "jwt-xyz")

        CaseRunner(sender, ctx).run(make_case(data={"token": "${token}"}))

        assert sender.calls[0]["data"] == {"token": "jwt-xyz"}

    def test_fail_fast_does_not_pollute_context(self, make_response) -> None:
        """校验不过就不写变量池 —— 免得脏 token 流到下一条用例（fail-fast）。"""
        sender = FakeSender(make_response({"msg": "登录失败", "token": None}))
        ctx = Context()
        case = make_case(
            validations=[{"contains": {"msg": "登录成功"}}],
            extracts={"token": "$.token"},
        )

        with pytest.raises(ValidationError):
            CaseRunner(sender, ctx).run(case)

        assert not ctx.exists("token")

    def test_param_slot_follows_method_and_content_type(self, make_response) -> None:
        """参数位置由适配层决定：表单走 data、json 走 json、GET 走 params。

        这条顺带把「决策归适配层」也测了 —— 发送端（假 Sender）收到的
        就已经是定好位置的参数，它不需要知道为什么。
        """
        sender = FakeSender(make_response({"msg": "ok"}))

        CaseRunner(sender, Context()).run(make_case(data={"a": 1}))
        assert "data" in sender.calls[0]

        CaseRunner(sender, Context()).run(
            make_case(headers={"Content-Type": "application/json"}, data={"a": 1})
        )
        assert "json" in sender.calls[1]

        CaseRunner(sender, Context()).run(make_case(method="GET", data={"a": 1}))
        assert "params" in sender.calls[2]
