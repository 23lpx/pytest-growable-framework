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
    # 带默认值的字段必须放最后（dataclass 的规则）；老 yaml 不写 extract / db / path_params 就是空
    extracts: dict = field(default_factory=dict)
    db_validations: list = field(default_factory=list)
    # 路径参数：把 url 里的 {占位符} 换成值。见 RequestHandler._build_path
    path_params: dict = field(default_factory=dict)
    # 用例级请求头：**覆盖**接口级同名项。同一个接口的用例，鉴权往往不同 ——
    # 「正常」带 A 的 token、「越权」带 B 的、「未登录」干脆不带，
    # 光靠接口级的 base_info.headers 表达不了。
    headers: dict = field(default_factory=dict)
    # 已知缺陷标记：填了原因就表示「这条现在注定不过，但**判据本身是对的**」。
    # 消费方（cases/）据此挂 pytest 的 xfail —— 它红了不算失败，而哪天被修好，
    # pytest 会以 XPASS 提醒你把标记摘掉。不填就是正常用例。
    xfail: str = ""
    # 冒烟标记：填 true 表示「核心路径，改完代码先跑这条」。
    # 和 xfail 同一个套路 —— yaml 里的元信息，由消费方（cases/）翻译成 pytest 标记。
    # ⚠️ 靠它的是 `-m smoke`，**不进冒烟集就别填** —— 冒烟集要能在两分钟内跑完，
    #    塞多了它就退化成"全量跑"，失去"改完先跑一遍"的意义。
    smoke: bool = False


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
                    db_validations=self._parse_db(case),
                    path_params=self._parse_path_params(case),
                    headers=self._parse_headers(case),
                    xfail=str(case.get('xfail', '') or ''),
                    smoke=bool(case.get('smoke', False)),
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

    @staticmethod
    def _parse_db(case: dict) -> list:
        """取用例的 db 段（「查哪张表、什么条件、期望什么」的规则列表）。

        和 _parse_extracts 同理：形状不对要在**解析期**暴露，
        别等到运行期才炸。老 yaml 不写 db 就是空列表，零改动兼容。
        """
        db_validations = case.get('db', [])
        if not isinstance(db_validations, list):
            raise CaseParseError(f"db 必须是列表: {db_validations!r}")
        return db_validations

    @staticmethod
    def _parse_path_params(case: dict) -> dict:
        """取用例的 path_params 段（占位符名 -> 值）。

        形状不对要在**解析期**暴露 —— 同 _parse_db。老 yaml 不写就是空 dict。
        """
        path_params = case.get('path_params', {})
        if not isinstance(path_params, dict):
            raise CaseParseError(f"path_params 必须是键值对: {path_params!r}")
        return path_params

    @staticmethod
    def _parse_headers(case: dict) -> dict:
        """取用例级请求头（可选，覆盖接口级同名项）。老 yaml 不写就是空。"""
        headers = case.get('headers', {})
        if not isinstance(headers, dict):
            raise CaseParseError(f"用例级 headers 必须是键值对: {headers!r}")
        return headers
