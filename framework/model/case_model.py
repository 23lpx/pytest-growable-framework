from dataclasses import dataclass

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
                    validations=case['validation']
                ))
        except (KeyError, TypeError) as e:
            raise CaseParseError(f"用例结构不符合规范，字段缺失或类型不对: {e}") from e
