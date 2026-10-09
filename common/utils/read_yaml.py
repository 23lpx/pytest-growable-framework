import yaml
from pathlib import Path

def _project_root() -> Path:
    cur = Path(__file__).resolve()
    for p in cur.parents:
        if (p / ".git").exists() or (p / ".venv").exists():
            return p
    raise RuntimeError("找不到项目根目录")

CASES_DIR = _project_root() / "data"

def read_case(file_name: str) -> dict:
    path = CASES_DIR / file_name
    print(path)
    if not path.exists():
        raise FileNotFoundError(f"用例文件不存在: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(e)
    if not isinstance(data, dict):
        raise ValueError(f"YAML 根节点必须是字典: {file_name}")
    return data


# if __name__ == "__main__":
#     case_data = read_case("login_cases.yaml")
#     print(type(case_data))
#     print(case_data)