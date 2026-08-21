from __future__ import annotations

import os
import signal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from prefect.runner import _workspace_supervisor
from prefect.runner._workspace_resolver import PreparedWorkspace
from prefect.runner._workspace_runtime import (
    PreparedWorkspaceManifest,
    WorkspaceSupervisorConfig,
    read_model,
)
from prefect.runner._workspace_supervisor import main, supervise
from prefect.utilities.processutils import get_sys_executable

pytestmark = pytest.mark.clear_db


class FakeProcess:
    returncode = 0

    async def wait(self) -> int:
        return self.returncode

    async def aclose(self) -> None:
        pass


def _workspace(tmp_path: Path) -> PreparedWorkspace:
    project = tmp_path / "checkout"
    project.mkdir()
    return PreparedWorkspace(
        workspace_root=tmp_path,
        working_directory=project,
        project_root=project,
        runtime_entrypoint="flows.py:hello",
        environment={
            **os.environ,
            "PATH": "/job/bin",
            "PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES": "true",
        },
        sys_path=[str(project)],
    )


async def test_supervisor_selects_uv_after_workspace_preparation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATH", "/job/bin")
    monkeypatch.setenv("PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES", "true")
    workspace = _workspace(tmp_path)
    workspace.environment["PATH"] = "/pull-step/bin"
    workspace.environment["PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES"] = "false"
    assert workspace.project_root is not None
    workspace.project_root.joinpath("pyproject.toml").write_text(
        "[project]\n"
        "name = 'test-project'\n"
        "version = '0.1.0'\n"
        "dependencies = ['prefect']\n"
    )
    prepare = AsyncMock(return_value=workspace)
    captured: dict[str, object] = {}

    async def open_process(command: list[str], **kwargs: object) -> FakeProcess:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(
        "prefect.runner._workspace_supervisor.prepare_workspace_for_flow_run",
        prepare,
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_supervisor.anyio.open_process", open_process
    )
    monkeypatch.setattr(
        "prefect.runner._uv_command.shutil.which",
        lambda executable, path=None: (
            "/job/bin/uv" if executable == "uv" and path == "/job/bin" else None
        ),
    )
    config = WorkspaceSupervisorConfig(
        flow_run_id=uuid4(),
        workspace_root=tmp_path,
        manifest_path=tmp_path / "manifest.json",
    )

    assert await supervise(config) == 0

    prepare.assert_awaited_once_with(config.flow_run_id, tmp_path)
    assert captured["command"] == [
        "/job/bin/uv",
        "run",
        "--no-default-groups",
        "--project",
        str(workspace.project_root),
        str(
            Path(_workspace_supervisor.__file__).with_name(
                "_workspace_runtime_bootstrap.py"
            )
        ),
        "engine",
        workspace.runtime_entrypoint,
    ]
    assert captured["kwargs"]["cwd"] == workspace.working_directory
    assert captured["kwargs"]["env"]["PATH"] == "/job/bin"
    manifest = read_model(config.manifest_path, PreparedWorkspaceManifest)
    assert manifest.environment == captured["kwargs"]["env"]
    assert manifest.hook_command == [
        "/job/bin/uv",
        "run",
        "--no-default-groups",
        "--project",
        str(workspace.project_root),
        str(
            Path(_workspace_supervisor.__file__).with_name(
                "_workspace_runtime_bootstrap.py"
            )
        ),
        "hook",
    ]


async def test_supervisor_restores_runner_owned_environment_after_preparation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _workspace(tmp_path)
    flow_run_id = uuid4()
    monkeypatch.setenv("PREFECT__FLOW_RUN_ID", str(flow_run_id))
    monkeypatch.setenv("PREFECT__CONTROL_TOKEN", "runner-token")
    monkeypatch.setenv("PATH", "/runner/bin")
    monkeypatch.setenv("PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES", "false")
    monkeypatch.delenv("PREFECT__CONTROL_PORT", raising=False)
    workspace.environment.update(
        {
            "PREFECT__FLOW_RUN_ID": str(uuid4()),
            "PREFECT__CONTROL_TOKEN": "project-token",
            "PREFECT__CONTROL_PORT": "4321",
            "PATH": "/project/bin",
            "PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES": "true",
            "PROJECT_ENV": "preserved",
        }
    )
    captured: dict[str, object] = {}

    async def open_process(command: list[str], **kwargs: object) -> FakeProcess:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(
        "prefect.runner._workspace_supervisor.prepare_workspace_for_flow_run",
        AsyncMock(return_value=workspace),
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_supervisor.anyio.open_process", open_process
    )
    monkeypatch.setattr(
        "prefect.runner._uv_command.shutil.which",
        lambda *_args, **_kwargs: pytest.fail(
            "uv should not be checked when the job disables auto-installation"
        ),
    )
    config = WorkspaceSupervisorConfig(
        flow_run_id=flow_run_id,
        workspace_root=tmp_path,
        manifest_path=tmp_path / "manifest.json",
    )

    assert await supervise(config) == 0

    environment = captured["kwargs"]["env"]
    assert environment["PREFECT__FLOW_RUN_ID"] == str(flow_run_id)
    assert environment["PREFECT__CONTROL_TOKEN"] == "runner-token"
    assert "PREFECT__CONTROL_PORT" not in environment
    assert environment["PREFECT__ENABLE_CANCELLATION_AND_CRASHED_HOOKS"] == "false"
    assert environment["PATH"] == "/runner/bin"
    assert environment["PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES"] == "false"
    assert environment["PROJECT_ENV"] == "preserved"
    assert captured["command"] == [get_sys_executable(), "-m", "prefect.engine"]


async def test_supervisor_preserves_explicit_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _workspace(tmp_path)
    captured: dict[str, object] = {}

    async def open_process(command: list[str], **kwargs: object) -> FakeProcess:
        captured["command"] = command
        return FakeProcess()

    monkeypatch.setattr(
        "prefect.runner._workspace_supervisor.prepare_workspace_for_flow_run",
        AsyncMock(return_value=workspace),
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_supervisor.anyio.open_process", open_process
    )
    config = WorkspaceSupervisorConfig(
        flow_run_id=uuid4(),
        workspace_root=tmp_path,
        manifest_path=tmp_path / "manifest.json",
        command="python custom.py --flag",
    )

    assert await supervise(config) == 0

    assert captured["command"] == ["python", "custom.py", "--flag"]
    manifest = read_model(config.manifest_path, PreparedWorkspaceManifest)
    assert manifest.hook_command is None


def test_main_propagates_engine_signal_to_supervisor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kill = MagicMock()
    monkeypatch.setattr(
        "prefect.runner._workspace_supervisor.anyio.run",
        lambda *_args: -signal.SIGTERM,
    )
    monkeypatch.setattr(
        os,
        "kill",
        kill,
    )

    assert main([]) == -signal.SIGTERM
    kill.assert_called_once_with(os.getpid(), signal.SIGTERM)
