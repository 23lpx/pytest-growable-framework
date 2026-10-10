from dataclasses import dataclass, field

import pytest
from _pytest.mark.structures import ParameterSet

from framework.model.case_model import CaseModel


@dataclass
class ExecuteCase:
    """一条可执行用例：接口级信息 + 用例级信息，合成一个自足的单元。

    它是 pytest 与 Runner 之间的契约：
      - pytest 拿它做参数化（一条 pytest 节点 = 一个 ExecuteCase）
      - Runner 只认它，从里面取 url/method/headers/data 就能发请求

    适配职责都收在这个类里（下面两个方法）：
      - from_model()      : CaseModel  -> list[ExecuteCase]
      - to_pytest_param() : ExecuteCase -> pytest.param
    以后不跑 pytest 了，就再加一个 to_xxx()，CaseModel 不用动。
    """

    # ⚠️ 字段须与 framework/contracts.py 的 CaseLike、context/replacer.py 的
    #    ResolvedCase 保持一致（三处同步改）

    # 接口级
    api_name: str
    url: str
    method: str
    headers: dict

    # 用例级
    case_name: str
    data: dict
    validations: list
    # 带默认值的字段必须放最后，否则 dataclass 报 non-default argument follows default
    extracts: dict = field(default_factory=dict)

    @classmethod
    def from_model(cls, case_model: CaseModel) -> "list[ExecuteCase]":
        api = case_model.api
        return [
            cls(
                api_name=api.api_name,
                url=api.url,
                method=api.method,
                headers=api.headers,
                case_name=c.case_name,
                data=c.data,
                validations=c.validations,
                extracts=c.extracts,
            )
            for c in case_model.cases
        ]

    def to_pytest_param(self) -> ParameterSet:
        return pytest.param(self, id=self.case_name)
