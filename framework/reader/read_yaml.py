import yaml

from framework.exception.errors import YamlReadError
from framework.infra.path import _project_root


class YamlRead:

    @staticmethod
    def read(file_path: str) -> dict:
        # 统一按「相对项目根」处理：写成 /data/x.yaml 或 data/x.yaml 都行。
        # 不剥前导斜杠的话，pathlib 会把它当成绝对路径，把项目根整个顶掉
        path = _project_root() / file_path.lstrip("/\\")
        if not path.exists():
            raise YamlReadError(f"用例文件不存在: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise YamlReadError(f"YAML 格式错误: {file_path}") from e
        except UnicodeDecodeError as e:
            raise YamlReadError(f"文件编码错误（应为 utf-8）: {file_path}") from e

        return data