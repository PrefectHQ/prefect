import sys
from pathlib import Path

from prefect import flow


@flow
def hello() -> str:
    project_root = Path("/opt/prefect/flow")
    assert Path.cwd() == project_root, f"Expected cwd {project_root}, got {Path.cwd()}"
    assert not (project_root / ".venv").exists(), (
        ".venv was created under project root — uv run was not skipped"
    )
    assert ".venv" not in Path(sys.executable).parts, (
        f"sys.executable is inside a .venv: {sys.executable}"
    )
    return sys.executable
