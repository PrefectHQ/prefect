"""Runs inside the pre-built container to verify the production code path.

Exercises the actual _uv_run_command() and _find_prematerialized_python()
from the installed prefect to prove that pre-built image deployments skip
uv run and use an explicit python command instead.

Also demonstrates that uv run would create a redundant .venv (proving the
skip is justified).
"""

import json
import subprocess
import sys
from pathlib import Path

from prefect.runner._workspace_resolver import PreparedWorkspace
from prefect.runner._workspace_starter import (
    _find_prematerialized_python,
    _uv_run_command,
)
from prefect.utilities.processutils import command_from_string

workdir = Path("/opt/prefect/flow")

workspace = PreparedWorkspace(
    workspace_root=workdir,
    working_directory=workdir,
    project_root=workdir,
    runtime_entrypoint="flows.py:hello",
    environment=dict(__import__("os").environ),
    sys_path=[],
)

# 1. Check if _find_prematerialized_python detects the environment
python_found = _find_prematerialized_python(workspace)

# 2. Check what _uv_run_command returns (should be explicit python, not uv run)
command = _uv_run_command(workspace)
command_parts = command_from_string(command) if command else None
uses_uv_run = command_parts is not None and command_parts[0] != "uv"

# 3. Verify uv run would create a redundant .venv
venv_before = (workdir / ".venv").exists()
subprocess.run(
    ["uv", "run", "--project", str(workdir), "python", "-c", "pass"],
    capture_output=True,
)
venv_after = (workdir / ".venv").exists()

print(
    json.dumps(
        {
            "python_found": python_found,
            "command": command,
            "command_parts": command_parts,
            "skips_uv_run": command_parts is not None and command_parts[0] != "uv",
            "venv_existed_before": venv_before,
            "venv_created_by_uv_run": not venv_before and venv_after,
            "sys_executable": sys.executable,
        }
    )
)
