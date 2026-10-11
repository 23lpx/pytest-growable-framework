from dataclasses import dataclass, field

from pytest_framework.entities.exception.errors import CaseParseError
from pytest_framework.infrastructure.path import _project_root
from pytest_framework.adapters.reader import YamlRead


@dataclass
class ApiCase:
    api_name: str
    url: str
    method: str
    headers: dict


@dataclass
class TestCase:
    case_name: str
    data: dict
    validations: list
    # 带默认值的字段必须放最后（dataclass 的规则）；老 yaml 不写 extract 就是空 dict
    extracts: dict = field(default_factory=dict)


class CaseModel:
    """统一数据模型：把散乱数据源（yaml/json/...）的数据，封装成一个规范结构。

    只负责「封装」，不做适配 —— 适配（-> pytest 等）交给 ExecuteCase。

    一个实例 = **一个接口 + 它的若干条用例**。
    """

    def __init__(self, file_path: str) -> None:
        self.api = None
        self.cases = []
        self.parse(YamlRead.read(file_path))

    @classmethod
    def from_dict(cls, data: dict) -> "CaseModel":
        """从已经读进来的 dict 构造。

        给场景层用：场景 yaml 的每个元素就是「单接口形态」的 dict，
        直接交给这个解析器，不重复实现一套。
        """
        model = cls.__new__(cls)  # 跳过 __init__：它要文件路径，而这里已经有数据了
        model.api = None
        model.cases = []
        model.parse(data)
        return model

    @classmethod
    def discover(cls, dir_path: str = "data/api") -> "list[CaseModel]":
        """扫描目录下所有单接口 yaml —— **一个文件 = 一个接口的用例集**。

        与 ScenarioModel.discover 对称：加接口 = 丢一个 yaml 进 data/api/，不碰代码。

        ⚠️ 在**收集阶段**执行（模块导入时求值）：某个 yaml 坏了会让整个测试文件
        collection error —— pytest 收集是「全有全无」。先接受，等数据多了再上 schema 校验。
        """
        root = _project_root() / dir_path
        if not root.exists():
            return []
        return [cls(f"{dir_path}/{p.name}") for p in sorted(root.glob("*.yaml"))]

    def parse(self, data: dict) -> None:
        """把「一个接口的 dict」（base_info + test_cases）解析成 ApiCase + list[TestCase]。

        独立成方法是为了让场景层能复用 —— 场景的每个 step 就是这样一个 dict。
        """
        try:
            base_info = data['base_info']
            test_cases = data['test_cases']

            self.api = ApiCase(
                api_name=base_info['api_name'],
                url=base_info['url'],
                headers=base_info['headers'],
                method=base_info['method'],
            )
            for case in test_cases:
                self.cases.append(TestCase(
                    case_name=case['case_name'],
                    data=case['data'],
                    validations=case['validation'],
                    extracts=self._parse_extracts(case),
                ))
        except (KeyError, TypeError) as e:
            raise CaseParseError(f"用例结构不符合规范，字段缺失或类型不对: {e}") from e

    @staticmethod
    def _parse_extracts(case: dict) -> dict:
        """取用例的 extract 段（变量名 -> jsonpath 表达式）。

        写成独立方法是为了让「extract 不是键值对」这种手误在**解析期**就暴露，
        而不是等到运行期 items() 抛 AttributeError。
        CaseParseError 不是 KeyError/TypeError，会穿过外层的 except 直接冒出去。
        """
        extracts = case.get('extract', {})
        if not isinstance(extracts, dict):
            raise CaseParseError(f"extract 必须是 键值对: {extracts!r}")
        return extracts
