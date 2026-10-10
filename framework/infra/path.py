from pathlib import Path

def _project_root() -> Path:
    cur = Path(__file__).resolve()
    for p in cur.parents:
        if (p / ".git").exists() or (p / ".venv").exists():
            return p
    raise RuntimeError("找不到项目根目录")