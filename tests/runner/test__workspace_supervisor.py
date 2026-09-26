from __future__ import annotations

import os
import signal
import sys
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


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process handoff")
async def test_engine_launch_replaces_supervisor_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    chdir = MagicMock()
    execvpe = MagicMock(side_effect=RuntimeError("exec called"))
    monkeypatch.setattr(_workspace_supervisor.os, "chdir", chdir)
    monkeypatch.setattr(_workspace_supervisor.os, "execvpe", execvpe)

    command = ["/project/bin/python", "-m", "prefect.flow_engine"]
    environment = {"PATH": "/project/bin"}
    with pytest.raises(RuntimeError, match="exec called"):
        await _workspace_supervisor._launch_engine(
            command,
            cwd=tmp_path,
            environment=environment,
        )

    chdir.assert_called_once_with(tmp_path)
    execvpe.assert_called_once_with(command[0], command, environment)


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

    async def launch_engine(
        command: list[str], *, cwd: Path, environment: dict[str, str]
    ) -> int:
        captured["command"] = command
        captured["kwargs"] = {"cwd": cwd, "env": environment}
        return 0

    monkeypatch.setattr(
        "prefect.runner._workspace_supervisor.prepare_workspace_for_flow_run",
        prepare,
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_supervisor._launch_engine", launch_engine
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
    runner_attribution = {
        "PREFECT__WORKER_ID": "runner-worker-id",
        "PREFECT__WORKER_NAME": "runner-worker",
        "PREFECT__FLOW_ID": "runner-flow-id",
        "PREFECT__FLOW_NAME": "runner-flow",
        "PREFECT__DEPLOYMENT_ID": "runner-deployment-id",
        "PREFECT__DEPLOYMENT_NAME": "runner-deployment",
    }
    for key, value in runner_attribution.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("PREFECT__FLOW_RUN_ID", str(flow_run_id))
    monkeypatch.setenv("PREFECT__CONTROL_TOKEN", "runner-token")
    monkeypatch.setenv("PATH", "/runner/bin")
    monkeypatch.setenv("PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES", "false")
    monkeypatch.setenv("PREFECT_API_URL", "https://runner.example/api")
    monkeypatch.setenv("PREFECT_API_KEY", "runner-key")
    monkeypatch.setenv("PREFECT_API_TLS_INSECURE_SKIP_VERIFY", "false")
    monkeypatch.delenv("PREFECT__CONTROL_PORT", raising=False)
    monkeypatch.delenv("PREFECT_API_SSL_CERT_FILE", raising=False)
    workspace.environment.update(
        {
            "PREFECT__FLOW_RUN_ID": str(uuid4()),
            "PREFECT__CONTROL_TOKEN": "project-token",
            "PREFECT__CONTROL_PORT": "4321",
            "PATH": "/project/bin",
            "PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES": "true",
            "PREFECT_API_URL": "https://project.example/api",
            "PREFECT_API_KEY": "project-key",
            "PREFECT_API_TLS_INSECURE_SKIP_VERIFY": "true",
            "PREFECT_API_SSL_CERT_FILE": "/project/ca.pem",
            "PROJECT_ENV": "preserved",
            **{key: f"project-{value}" for key, value in runner_attribution.items()},
        }
    )
    captured: dict[str, object] = {}

    async def launch_engine(
        command: list[str], *, cwd: Path, environment: dict[str, str]
    ) -> int:
        captured["command"] = command
        captured["kwargs"] = {"cwd": cwd, "env": environment}
        return 0

    monkeypatch.setattr(
        "prefect.runner._workspace_supervisor.prepare_workspace_for_flow_run",
        AsyncMock(return_value=workspace),
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_supervisor._launch_engine", launch_engine
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
    assert environment["PREFECT_API_URL"] == "https://runner.example/api"
    assert environment["PREFECT_API_KEY"] == "runner-key"
    assert environment["PREFECT_API_TLS_INSECURE_SKIP_VERIFY"] == "false"
    assert "PREFECT_API_SSL_CERT_FILE" not in environment
    assert environment["PROJECT_ENV"] == "preserved"
    assert {key: environment[key] for key in runner_attribution} == runner_attribution
    assert captured["command"] == [get_sys_executable(), "-m", "prefect.engine"]


async def test_supervisor_preserves_explicit_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _workspace(tmp_path)
    captured: dict[str, object] = {}

    async def launch_engine(
        command: list[str], *, cwd: Path, environment: dict[str, str]
    ) -> int:
        captured["command"] = command
        return 0

    monkeypatch.setattr(
        "prefect.runner._workspace_supervisor.prepare_workspace_for_flow_run",
        AsyncMock(return_value=workspace),
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_supervisor._launch_engine", launch_engine
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


def test_main_enters_windows_job_before_supervision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, int] | str] = []
    termination_scope = MagicMock()

    monkeypatch.setattr(
        _workspace_supervisor,
        "sys",
        MagicMock(platform="win32"),
    )
    monkeypatch.setattr(
        _workspace_supervisor,
        "create_isolated_termination_scope",
        lambda pid: events.append(("job", pid)) or termination_scope,
        raising=False,
    )
    monkeypatch.setattr(
        _workspace_supervisor.anyio,
        "run",
        lambda *_args: events.append("supervise") or 0,
    )

    assert main([]) == 0
    assert events == [("job", os.getpid()), "supervise"]
    termination_scope.close.assert_not_called()
