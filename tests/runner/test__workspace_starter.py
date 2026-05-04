from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from prefect.runner._workspace_resolver import (
    PreparedWorkspace,
    PreparedWorkspaceError,
    PreparedWorkspaceResult,
)
from prefect.runner._workspace_starter import (
    WorkspaceResolvingEngineCommandStarter,
    load_flow_from_prepared_workspace,
    resolve_workspace_in_subprocess,
    workspace_environment,
)
from prefect.utilities.filesystem import tmpchdir


def _prepared_workspace(tmp_path: Path) -> PreparedWorkspace:
    workspace_root = tmp_path / "workspace"
    working_directory = workspace_root / "project"
    working_directory.mkdir(parents=True)
    return PreparedWorkspace(
        workspace_root=workspace_root,
        working_directory=working_directory,
        project_root=working_directory,
        runtime_entrypoint="flows.py:hello",
        environment={**os.environ, "WORKSPACE_TEST_ENV": "1"},
        sys_path=[str(tmp_path / "support")],
    )


def test_workspace_environment_prepends_workspace_paths(tmp_path: Path):
    workspace = _prepared_workspace(tmp_path)
    workspace.environment["PYTHONPATH"] = str(tmp_path / "existing")

    environment = workspace_environment(workspace)
    pythonpath = environment["PYTHONPATH"].split(os.pathsep)

    assert environment["WORKSPACE_TEST_ENV"] == "1"
    assert pythonpath[:3] == [
        str(workspace.working_directory),
        str(tmp_path / "support"),
        str(tmp_path / "existing"),
    ]


async def test_resolve_workspace_in_subprocess_returns_success_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    captured: dict[str, object] = {}

    async def fake_run_process(command: list[str], **kwargs: object):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=PreparedWorkspaceResult(status="success", workspace=workspace)
            .model_dump_json()
            .encode(),
            stderr=b"",
        )

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.anyio.run_process", fake_run_process
    )

    result = await resolve_workspace_in_subprocess(uuid4(), tmp_path / "workspace")

    assert result == workspace
    assert "prefect.runner._workspace_resolver" in captured["command"]
    assert captured["kwargs"]["stdout"] == subprocess.PIPE
    assert captured["kwargs"]["stderr"] == subprocess.PIPE
    assert "env" in captured["kwargs"]
    assert captured["kwargs"]["check"] is False


async def test_resolve_workspace_in_subprocess_raises_structured_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    command = ["python", "-m", "prefect.runner._workspace_resolver"]
    result = PreparedWorkspaceResult(
        status="error",
        error=PreparedWorkspaceError(
            error_type="StepExecutionError",
            error_message="pull failed",
            cause_type="RuntimeError",
            cause_message="boom",
        ),
    )

    async def fake_run_process(*args: object, **kwargs: object):
        return subprocess.CompletedProcess(
            command,
            1,
            stdout=result.model_dump_json().encode(),
            stderr=b"",
        )

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.anyio.run_process", fake_run_process
    )

    with pytest.raises(RuntimeError, match="StepExecutionError: pull failed"):
        await resolve_workspace_in_subprocess(uuid4(), tmp_path / "workspace")


async def test_workspace_resolving_starter_delegates_to_engine_starter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    resolver = AsyncMock(return_value=workspace)
    flow_run = MagicMock()
    flow_run.id = uuid4()
    instances: list[object] = []

    class FakeEngineCommandStarter:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            instances.append(self)

        async def start(self, flow_run_arg: object, task_status: object) -> None:
            self.flow_run = flow_run_arg
            self.task_status = task_status

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.resolve_workspace_in_subprocess", resolver
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_starter.EngineCommandStarter",
        FakeEngineCommandStarter,
    )

    starter = WorkspaceResolvingEngineCommandStarter(
        workspace_root=tmp_path / "workspace-root"
    )
    await starter.start(flow_run)

    assert starter.workspace == workspace
    resolver.assert_awaited_once_with(flow_run.id, tmp_path / "workspace-root")
    assert len(instances) == 1
    engine_starter = instances[0]
    assert engine_starter.kwargs["cwd"] == workspace.working_directory
    assert engine_starter.kwargs["entrypoint"] == workspace.runtime_entrypoint
    assert engine_starter.kwargs["env"]["WORKSPACE_TEST_ENV"] == "1"
    assert engine_starter.flow_run is flow_run


async def test_load_flow_from_prepared_workspace_does_not_change_parent_cwd(
    tmp_path: Path,
):
    workspace = _prepared_workspace(tmp_path)
    flow_file = workspace.working_directory / "flows.py"
    flow_file.write_text(
        "from prefect import flow\n\n@flow\ndef hello():\n    return 'hello'\n"
    )
    parent_cwd = tmp_path / "parent-cwd"
    parent_cwd.mkdir()
    original_sys_path = list(sys.path)

    with tmpchdir(parent_cwd):
        flow = await load_flow_from_prepared_workspace(workspace)
        assert Path.cwd() == parent_cwd.resolve()

    assert flow.name == "hello"
    assert sys.path == original_sys_path


async def test_load_flow_from_prepared_workspace_preserves_module_entrypoint(
    tmp_path: Path,
):
    workspace = _prepared_workspace(tmp_path)
    package = workspace.working_directory / "package"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "module.py").write_text(
        "from prefect import flow\n\n@flow\ndef hello():\n    return 'hello'\n"
    )
    workspace.runtime_entrypoint = "package.module:hello"
    parent_cwd = tmp_path / "parent-cwd"
    parent_cwd.mkdir()
    original_sys_path = list(sys.path)

    with tmpchdir(parent_cwd):
        flow = await load_flow_from_prepared_workspace(workspace)
        assert Path.cwd() == parent_cwd.resolve()

    assert flow.name == "hello"
    assert sys.path == original_sys_path
