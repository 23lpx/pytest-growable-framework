from pathlib import Path

from framework.exception.errors import CaseParseError
from framework.infra.path import _project_root
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

    @classmethod
    def discover(cls, dir_path: str = "data/scenarios") -> "list[ScenarioModel]":
        """扫描目录下所有场景 yaml —— **加一个文件就多一个场景用例，不用碰代码**。

        路径给「相对项目根」的形式，交给 YamlRead 统一拼接（它内部会 lstrip 掉前导斜杠）。

        ⚠️ 这个方法在**收集阶段**执行（模块导入时就被 pytest 求值）：
        某个 yaml 坏了会让**整个测试文件** collection error —— pytest 的收集是
        「全有全无」。这是数据驱动的固有代价，先接受；等数据规模上来，
        再上 schema 校验把错误提前暴露成人话。
        """
        root = _project_root() / dir_path
        if not root.exists():
            return []
        return [cls(f"{dir_path}/{p.name}") for p in sorted(root.glob("*.yaml"))]
