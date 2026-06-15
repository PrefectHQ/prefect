from __future__ import annotations

import os
import subprocess
import sys
import sysconfig
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
    _workspace_command,
    load_flow_from_prepared_workspace,
    resolve_workspace_in_subprocess,
    workspace_environment,
)
from prefect.settings import (
    PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES,
    temporary_settings,
)
from prefect.utilities.filesystem import tmpchdir
from prefect.utilities.processutils import command_from_string

pytestmark = pytest.mark.clear_db


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


def test_workspace_command_uses_uv_for_pyproject_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    workspace.environment["PATH"] = "/workspace/bin"
    (workspace.project_root / "pyproject.toml").write_text(
        "[project]\n"
        "name = 'test-project'\n"
        "version = '0.1.0'\n"
        "dependencies = ['prefect']\n"
    )
    captured_paths: list[str | None] = []

    def fake_which(executable: str, path: str | None = None) -> str | None:
        captured_paths.append(path)
        return "/opt/bin/uv" if executable == "uv" else None

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        fake_which,
    )

    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: True}):
        command = _workspace_command(workspace, explicit_command=None)

    assert captured_paths == [workspace.environment["PATH"]]
    assert command is not None
    assert command_from_string(command) == [
        "/opt/bin/uv",
        "run",
        "--no-default-groups",
        "--project",
        str(workspace.project_root),
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]


def test_workspace_command_falls_back_without_pyproject(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: True}):
        assert _workspace_command(workspace, explicit_command=None) is None


def test_workspace_command_falls_back_without_prefect_dependency(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    (workspace.project_root / "pyproject.toml").write_text(
        "[project]\nname = 'test-project'\nversion = '0.1.0'\ndependencies = []\n"
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: True}):
        assert _workspace_command(workspace, explicit_command=None) is None


def test_workspace_command_falls_back_without_uv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    (workspace.project_root / "pyproject.toml").write_text(
        "[project]\n"
        "name = 'test-project'\n"
        "version = '0.1.0'\n"
        "dependencies = ['prefect']\n"
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: None,
    )

    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: True}):
        assert _workspace_command(workspace, explicit_command=None) is None


def test_workspace_command_does_not_auto_install_dependencies_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    (workspace.project_root / "pyproject.toml").write_text(
        "[project]\n"
        "name = 'test-project'\n"
        "version = '0.1.0'\n"
        "dependencies = ['prefect']\n"
    )

    def fail_if_checked(*args: object, **kwargs: object) -> None:
        raise AssertionError("uv should not be checked unless auto-install is enabled")

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        fail_if_checked,
    )

    assert _workspace_command(workspace, explicit_command=None) is None


def test_workspace_command_preserves_explicit_command(tmp_path: Path):
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    (workspace.project_root / "pyproject.toml").write_text(
        "[project]\nname = 'test-project'\nversion = '0.1.0'\ndependencies = []\n"
    )

    assert (
        _workspace_command(workspace, explicit_command="python custom.py")
        == "python custom.py"
    )


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
        workspace_root=tmp_path / "workspace-root",
        deployment_name="workspace-deployment",
    )
    await starter.start(flow_run)

    assert starter.workspace == workspace
    resolver.assert_awaited_once_with(flow_run.id, tmp_path / "workspace-root")
    assert len(instances) == 1
    engine_starter = instances[0]
    assert engine_starter.kwargs["command"] is None
    assert engine_starter.kwargs["cwd"] == workspace.working_directory
    assert engine_starter.kwargs["entrypoint"] == workspace.runtime_entrypoint
    assert engine_starter.kwargs["env"]["WORKSPACE_TEST_ENV"] == "1"
    assert engine_starter.flow_run is flow_run


async def test_workspace_resolving_starter_uses_uv_for_pyproject_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    (workspace.project_root / "pyproject.toml").write_text(
        "[project]\n"
        "name = 'test-project'\n"
        "version = '0.1.0'\n"
        "dependencies = ['prefect']\n"
    )
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
    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    starter = WorkspaceResolvingEngineCommandStarter(
        workspace_root=tmp_path / "workspace-root",
        deployment_name="workspace-deployment",
    )
    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: True}):
        await starter.start(flow_run)

    assert len(instances) == 1
    command = instances[0].kwargs["command"]
    assert command is not None
    assert command_from_string(command) == [
        "/opt/bin/uv",
        "run",
        "--no-default-groups",
        "--project",
        str(workspace.project_root),
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]
    assert instances[0].kwargs["cwd"] == workspace.working_directory
    assert instances[0].kwargs["deployment_name"] == "workspace-deployment"


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


async def test_load_flow_from_prepared_workspace_preserves_stdlib_imports(
    tmp_path: Path,
) -> None:
    workspace = _prepared_workspace(tmp_path)
    workspace.sys_path = [sysconfig.get_paths()["stdlib"], *workspace.sys_path]
    flow_file = workspace.working_directory / "flows.py"
    flow_file.write_text(
        "import mailbox\n"
        "from prefect import flow\n\n"
        "@flow\n"
        "def hello():\n"
        "    return mailbox.Mailbox\n"
    )
    parent_cwd = tmp_path / "parent-cwd"
    parent_cwd.mkdir()
    original_sys_path = list(sys.path)
    original_mailbox = sys.modules.pop("mailbox", None)

    try:
        with tmpchdir(parent_cwd):
            flow = await load_flow_from_prepared_workspace(workspace)
            assert Path.cwd() == parent_cwd.resolve()
    finally:
        if original_mailbox is None:
            sys.modules.pop("mailbox", None)
        else:
            sys.modules["mailbox"] = original_mailbox

    assert flow.name == "hello"
    assert sys.path == original_sys_path


class TestWorkspaceEnvironmentPythonpathFiltering:
    def test_excludes_stdlib_from_pythonpath(self, tmp_path: Path) -> None:
        workspace = _prepared_workspace(tmp_path)
        stdlib = sysconfig.get_paths()["stdlib"]
        lib_dynload = os.path.join(stdlib, "lib-dynload")
        stdlib_zip = (
            Path(stdlib).parent
            / f"python{sys.version_info.major}{sys.version_info.minor}.zip"
        )
        adjacent_user_zip = Path(stdlib).parent / "python_helpers.zip"
        app_zip = tmp_path / "python_deps.zip"
        site_packages = sysconfig.get_paths()["purelib"]

        workspace.sys_path = [
            "",
            stdlib,
            lib_dynload,
            str(stdlib_zip),
            site_packages,
            str(adjacent_user_zip),
            str(app_zip),
            "/app",
        ]

        env = workspace_environment(workspace)
        pythonpath_entries = env["PYTHONPATH"].split(os.pathsep)

        resolved_stdlib = str(Path(stdlib).resolve())
        resolved_dynload = str(Path(lib_dynload).resolve())
        resolved_stdlib_zip = str(stdlib_zip.resolve())
        assert resolved_stdlib not in pythonpath_entries
        assert resolved_dynload not in pythonpath_entries
        assert resolved_stdlib_zip not in pythonpath_entries

        resolved_site = str(Path(site_packages).resolve())
        assert resolved_site in pythonpath_entries
        assert str(adjacent_user_zip) in pythonpath_entries
        assert str(app_zip) in pythonpath_entries

    def test_filters_stdlib_from_inherited_pythonpath(self, tmp_path: Path) -> None:
        workspace = _prepared_workspace(tmp_path)
        stdlib = sysconfig.get_paths()["stdlib"]
        stdlib_zip = (
            Path(stdlib).parent
            / f"python{sys.version_info.major}{sys.version_info.minor}.zip"
        )
        app_zip = tmp_path / "python_deps.zip"
        workspace.sys_path = ["/app"]
        workspace.environment["PYTHONPATH"] = os.pathsep.join(
            [stdlib, str(stdlib_zip), str(app_zip), "/extra"]
        )

        env = workspace_environment(workspace)
        pythonpath_entries = env["PYTHONPATH"].split(os.pathsep)

        resolved_stdlib = str(Path(stdlib).resolve())
        resolved_stdlib_zip = str(stdlib_zip.resolve())
        assert resolved_stdlib not in pythonpath_entries
        assert resolved_stdlib_zip not in pythonpath_entries
        assert str(app_zip) in pythonpath_entries
        assert "/extra" in pythonpath_entries
