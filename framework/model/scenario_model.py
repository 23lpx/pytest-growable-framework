from pathlib import Path

from framework.exception.errors import CaseParseError
from framework.model.case_model import CaseModel
from framework.reader.read_yaml import YamlRead


class ScenarioModel:
    """业务场景：一串**按顺序执行**的单接口用例集。

    根节点是**列表**，每个元素就是一个「单接口 yaml 的完整形态」
    （base_info + test_cases）。所以直接复用 CaseModel 解析 ——
    场景 = list[CaseModel]，是「拼积木」，不是另造一套解析器。

    与单接口的差别**不在数据形态，在消费方式**：
      单接口 -> pytest 参数化   -> 每条 case 一个节点（细粒度调度，保住 -k/-m）
      场景   -> ScenarioRunner -> 整个列表一个节点（顺序可控，贴近真实业务流）

    只做解析，不做编排 —— 编排是 ScenarioRunner 的事。
    """

    def __init__(self, file_path: str) -> None:
        # 场景名取文件名（yaml 根节点是列表，没地方放元数据）
        self.name = Path(file_path).stem
        raw = YamlRead.read(file_path)
        if not isinstance(raw, list):
            raise CaseParseError(
                f"场景 yaml 的根节点必须是列表（若干个接口块），实际是 {type(raw).__name__}: {file_path}"
            )
        self.steps = [CaseModel.from_dict(item) for item in raw]
