from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from prefect.runner._workspace_resolver import PreparedWorkspace
from prefect.runner._workspace_runtime import (
    PreparedWorkspaceManifest,
    WorkspaceSupervisorConfig,
    read_model,
)
from prefect.runner._workspace_supervisor import supervise
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
    workspace = _workspace(tmp_path)
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
        lambda executable, path=None: "/job/bin/uv" if executable == "uv" else None,
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
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]
    assert captured["kwargs"]["cwd"] == workspace.working_directory
    assert captured["kwargs"]["env"]["PATH"] == "/job/bin"
    manifest = read_model(config.manifest_path, PreparedWorkspaceManifest)
    assert manifest.hook_command_prefix == [
        "/job/bin/uv",
        "run",
        "--no-default-groups",
        "--project",
        str(workspace.project_root),
    ]


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
    assert manifest.hook_command_prefix == [get_sys_executable()]
