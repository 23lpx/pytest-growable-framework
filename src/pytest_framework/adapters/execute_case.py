from dataclasses import dataclass, field

from pytest_framework.entities.model.case_model import CaseModel


@dataclass
class ExecuteCase:
    """一条可执行用例：接口级信息 + 用例级信息，合成一个自足的单元。

    它是 pytest 与 Runner 之间的契约：
      - pytest 拿它做参数化（一条 pytest 节点 = 一个 ExecuteCase）
      - Runner 只认它，从里面取 url/method/headers/data 就能发请求

    适配职责收在这两个 classmethod 里：
      - from_model() : CaseModel -> list[ExecuteCase]
      - discover()   : 扫目录 + 展平

    ⚠️ 这里**不 import pytest** —— pytest 只是「谁消费它」（`cases/` 把它丢给
    parametrize），不是「它是什么」。原先有个 to_pytest_param() 顺手返回 pytest.param，
    但全仓没人调用，还牵进了 `_pytest.mark.structures` 这种私有 API，已删。
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
    db_validations: list = field(default_factory=list)
    path_params: dict = field(default_factory=dict)
    # 已知缺陷原因（非空 = 消费方该挂 xfail）。见 TestCase.xfail
    xfail: str = ""

    @classmethod
    def from_model(cls, case_model: CaseModel) -> "list[ExecuteCase]":
        api = case_model.api
        return [
            cls(
                api_name=api.api_name,
                url=api.url,
                method=api.method,
                # 用例级 headers 覆盖接口级 —— 同一个接口，鉴权常常因用例而异
                headers={**api.headers, **c.headers},
                case_name=c.case_name,
                data=c.data,
                validations=c.validations,
                extracts=c.extracts,
                db_validations=c.db_validations,
                path_params=c.path_params,
                xfail=c.xfail,
            )
            for c in case_model.cases
        ]

    @classmethod
    def discover(cls, dir_path: str = "data/api") -> "list[ExecuteCase]":
        """扫描目录，把每个接口文件的用例**展平**成可执行单元。

        单接口的粒度是「一条 case 一个节点」，所以要展平 ——
        不是把文件当一个节点（那是场景的做法，见 ScenarioModel.discover）。
        """
        cases: list[ExecuteCase] = []
        for model in CaseModel.discover(dir_path):
            cases.extend(cls.from_model(model))
        return cases
