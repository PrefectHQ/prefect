from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import anyio
import pytest

from prefect.client.schemas.objects import FlowRun
from prefect.runner import _workspace_hook_runner
from prefect.runner._workspace_hook_runner import WorkspaceHookRunner
from prefect.runner._workspace_runtime import (
    PreparedWorkspaceManifest,
    write_private_model,
)
from prefect.states import Crashed

pytestmark = pytest.mark.clear_db


def _runtime_hook_runner(
    tmp_path: Path, value: str
) -> tuple[WorkspaceHookRunner, Path]:
    project = tmp_path / value
    project.mkdir()
    dependencies = project / "runtime-dependencies"
    dependencies.mkdir()
    dependencies.joinpath("runtime_only_dependency.py").write_text(
        f"VALUE = {value!r}\n"
    )
    marker = project / "hook-ran.txt"
    project.joinpath("flows.py").write_text(
        "import os\n"
        "from pathlib import Path\n"
        "from prefect import flow\n\n"
        "def crashed_hook(flow, flow_run, state):\n"
        "    import runtime_only_dependency\n"
        "    Path(os.environ['HOOK_MARKER']).write_text(\n"
        "        runtime_only_dependency.VALUE\n"
        "    )\n\n"
        "@flow(on_crashed=[crashed_hook])\n"
        "def hello():\n"
        "    pass\n"
    )
    runtime = project / "selected-runtime"
    runtime.write_text(
        f"#!{sys.executable}\n"
        "import os\n"
        "import sys\n"
        f"dependency_path = {str(dependencies)!r}\n"
        "current_pythonpath = os.environ.get('PYTHONPATH', '')\n"
        "os.environ['PYTHONPATH'] = os.pathsep.join(\n"
        "    value for value in (dependency_path, current_pythonpath) if value\n"
        ")\n"
        "if '-m' in sys.argv:\n"
        "    module_index = sys.argv.index('-m')\n"
        "    if sys.argv[module_index + 1] == "
        "'prefect.runner._workspace_hook_runner':\n"
        "        raise SystemExit(91)\n"
        "script_index = next(\n"
        "    index for index, value in enumerate(sys.argv)\n"
        "    if value.endswith('_workspace_runtime_bootstrap.py')\n"
        ")\n"
        "os.execv(sys.executable, [sys.executable, *sys.argv[script_index:]])\n"
    )
    runtime.chmod(0o700)
    manifest_path = project / "workspace.json"
    write_private_model(
        manifest_path,
        PreparedWorkspaceManifest(
            working_directory=project,
            project_root=project,
            runtime_entrypoint="flows.py:hello",
            hook_command=[
                str(runtime),
                "run",
                "--no-default-groups",
                "--project",
                str(project),
                str(
                    Path(_workspace_hook_runner.__file__).with_name(
                        "_workspace_runtime_bootstrap.py"
                    )
                ),
                "hook",
            ],
            environment={
                **os.environ,
                "HOOK_MARKER": str(marker),
                "PYTHONPATH": str(project),
            },
        ),
    )
    return (
        WorkspaceHookRunner(
            manifest_path=manifest_path,
            stream_output=True,
        ),
        marker,
    )


async def test_hooks_use_selected_runtime_without_mutating_parent_globals(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert importlib.util.find_spec("runtime_only_dependency") is None
    monkeypatch.setenv("HOOK_MARKER", "parent-value")
    original_cwd = Path.cwd()
    original_sys_path = list(sys.path)
    first_runner, first_marker = _runtime_hook_runner(tmp_path, "first")
    second_runner, second_marker = _runtime_hook_runner(tmp_path, "second")
    flow_run = FlowRun(id=uuid4(), flow_id=uuid4(), name="hook-test")
    crashed = Crashed(message="infrastructure exited")

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(first_runner.run_crashed_hooks, flow_run, crashed)
        task_group.start_soon(second_runner.run_crashed_hooks, flow_run, crashed)

    assert first_marker.read_text() == "first"
    assert second_marker.read_text() == "second"
    assert os.environ["HOOK_MARKER"] == "parent-value"
    assert Path.cwd() == original_cwd
    assert sys.path == original_sys_path
    assert importlib.util.find_spec("runtime_only_dependency") is None


async def test_opaque_command_warns_instead_of_using_worker_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest_path = tmp_path / "workspace.json"
    write_private_model(
        manifest_path,
        PreparedWorkspaceManifest(
            working_directory=tmp_path,
            project_root=None,
            runtime_entrypoint="flows.py:hello",
            hook_command=None,
            environment=dict(os.environ),
        ),
    )
    logger = MagicMock()
    run_process = AsyncMock()
    monkeypatch.setattr(
        "prefect.runner._workspace_hook_runner.flow_run_logger",
        lambda _flow_run: logger,
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_hook_runner.run_process",
        run_process,
    )
    runner = WorkspaceHookRunner(manifest_path=manifest_path, stream_output=True)

    await runner.run_crashed_hooks(
        FlowRun(id=uuid4(), flow_id=uuid4(), name="hook-test"),
        Crashed(message="infrastructure exited"),
    )

    run_process.assert_not_awaited()
    logger.warning.assert_called_once()
    assert "does not expose a Python runtime" in logger.warning.call_args.args[0]
