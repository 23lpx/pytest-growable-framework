from dataclasses import dataclass, field

from framework.exception.errors import CaseParseError
from framework.reader.read_yaml import YamlRead


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
    """

    def __init__(self, file_path: str) -> None:
        self.api = None
        self.cases = []
        self.case_to_model(file_path)

    def case_to_model(self, file_path: str) -> None:
        data = YamlRead.read(file_path)
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

