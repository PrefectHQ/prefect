from __future__ import annotations

import os
import sys
import sysconfig
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import anyio
import pytest

from prefect.runner import _workspace_starter
from prefect.runner._process_manager import ProcessHandle
from prefect.runner._workspace_resolver import PreparedWorkspace
from prefect.runner._workspace_runtime import (
    WorkspaceSupervisorConfig,
    read_model,
)
from prefect.runner._workspace_starter import (
    WorkspaceResolvingEngineCommandStarter,
    _workspace_command,
    workspace_environment,
)
from prefect.settings import (
    PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES,
    temporary_settings,
)
from prefect.utilities.processutils import command_from_string, get_sys_executable

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
        "prefect.runner._uv_command.shutil.which",
        fake_which,
    )

    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: True}):
        command = _workspace_command(
            workspace,
            explicit_command=None,
            environment=workspace.environment,
        )

    assert captured_paths == [workspace.environment["PATH"]]
    assert command is not None
    assert command_from_string(command) == [
        "/opt/bin/uv",
        "run",
        "--no-default-groups",
        "--project",
        str(workspace.project_root),
        str(
            Path(_workspace_starter.__file__).with_name(
                "_workspace_runtime_bootstrap.py"
            )
        ),
        "engine",
        workspace.runtime_entrypoint,
    ]


def test_workspace_command_falls_back_without_pyproject(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    monkeypatch.setattr(
        "prefect.runner._uv_command.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: True}):
        assert (
            _workspace_command(
                workspace,
                explicit_command=None,
                environment=workspace.environment,
            )
            is None
        )


def test_workspace_command_falls_back_without_prefect_dependency(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    (workspace.project_root / "pyproject.toml").write_text(
        "[project]\nname = 'test-project'\nversion = '0.1.0'\ndependencies = []\n"
    )
    monkeypatch.setattr(
        "prefect.runner._uv_command.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: True}):
        assert (
            _workspace_command(
                workspace,
                explicit_command=None,
                environment=workspace.environment,
            )
            is None
        )


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
        "prefect.runner._uv_command.shutil.which",
        lambda executable, path=None: None,
    )

    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: True}):
        assert (
            _workspace_command(
                workspace,
                explicit_command=None,
                environment=workspace.environment,
            )
            is None
        )


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
        "prefect.runner._uv_command.shutil.which",
        fail_if_checked,
    )

    assert (
        _workspace_command(
            workspace,
            explicit_command=None,
            environment=workspace.environment,
        )
        is None
    )


def test_workspace_command_honors_effective_environment_setting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    workspace.environment["PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES"] = "false"
    workspace.project_root.joinpath("pyproject.toml").write_text(
        "[project]\n"
        "name = 'test-project'\n"
        "version = '0.1.0'\n"
        "dependencies = ['prefect']\n"
    )
    monkeypatch.setattr(
        "prefect.runner._uv_command.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: False}):
        command = _workspace_command(
            workspace,
            explicit_command=None,
            environment={
                **workspace.environment,
                "PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES": "true",
            },
        )

    assert command is not None
    assert command_from_string(command)[-3:] == [
        str(
            Path(_workspace_starter.__file__).with_name(
                "_workspace_runtime_bootstrap.py"
            )
        ),
        "engine",
        workspace.runtime_entrypoint,
    ]


def test_workspace_command_preserves_explicit_command(tmp_path: Path):
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    (workspace.project_root / "pyproject.toml").write_text(
        "[project]\nname = 'test-project'\nversion = '0.1.0'\ndependencies = []\n"
    )

    assert (
        _workspace_command(
            workspace,
            explicit_command="python custom.py",
            environment=workspace.environment,
        )
        == "python custom.py"
    )


@pytest.mark.parametrize(
    ("platform", "isolate_process_group"),
    [("linux", True), ("win32", False)],
)
async def test_workspace_resolving_starter_starts_managed_supervisor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: str,
    isolate_process_group: bool,
) -> None:
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
        "prefect.runner._workspace_starter.EngineCommandStarter",
        FakeEngineCommandStarter,
    )
    monkeypatch.setattr(
        _workspace_starter,
        "sys",
        MagicMock(platform=platform),
    )

    source_cwd = tmp_path / "source-cwd"
    source_cwd.mkdir()
    starter = WorkspaceResolvingEngineCommandStarter(
        workspace_root=tmp_path / "workspace-root",
        command="python custom.py",
        stream_output=False,
        deployment_name="workspace-deployment",
        source_cwd=source_cwd,
        environment={"WORKSPACE_CALLER_ENV": "caller"},
    )
    try:
        await starter.start(flow_run)
    finally:
        config_path = starter._config_path
        config = read_model(config_path, WorkspaceSupervisorConfig)
        starter.close()

    assert config.flow_run_id == flow_run.id
    assert config.workspace_root == tmp_path / "workspace-root"
    assert config.command == "python custom.py"
    assert len(instances) == 1
    engine_starter = instances[0]
    command = command_from_string(engine_starter.kwargs["command"])
    assert command[:3] == [
        get_sys_executable(),
        "-m",
        "prefect.runner._workspace_supervisor",
    ]
    assert command[3] == str(config_path)
    assert engine_starter.kwargs["cwd"] == source_cwd
    assert engine_starter.kwargs["env"] == {"WORKSPACE_CALLER_ENV": "caller"}
    assert engine_starter.kwargs["stream_output"] is False
    assert engine_starter.kwargs["isolate_process_group"] is isolate_process_group
    assert engine_starter.kwargs["env_overrides_settings"] is True
    assert engine_starter.flow_run is flow_run


async def test_workspace_starter_surfaces_handle_before_supervisor_finishes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    process = MagicMock(pid=42, returncode=None)
    expected_handle = ProcessHandle(process)
    release = anyio.Event()

    class GatedEngineCommandStarter:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def start(
            self,
            _flow_run: object,
            task_status: anyio.abc.TaskStatus[ProcessHandle],
        ) -> None:
            task_status.started(expected_handle)
            await release.wait()

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.EngineCommandStarter",
        GatedEngineCommandStarter,
    )
    flow_run = MagicMock(id=uuid4())
    starter = WorkspaceResolvingEngineCommandStarter(workspace_root=tmp_path)

    try:
        async with anyio.create_task_group() as task_group:
            with anyio.fail_after(1):
                handle = await task_group.start(starter.start, flow_run)
            assert handle is expected_handle
            release.set()
    finally:
        starter.close()


class TestWorkspaceEnvironmentPythonpathFiltering:
    def test_excludes_interpreter_paths_from_pythonpath(self, tmp_path: Path) -> None:
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
        assert resolved_site not in pythonpath_entries
        assert str(adjacent_user_zip) in pythonpath_entries
        assert str(app_zip) in pythonpath_entries

    def test_filters_stdlib_from_inherited_pythonpath(self, tmp_path: Path) -> None:
        workspace = _prepared_workspace(tmp_path)
        stdlib = sysconfig.get_paths()["stdlib"]
        site_packages = sysconfig.get_paths()["purelib"]
        stdlib_zip = (
            Path(stdlib).parent
            / f"python{sys.version_info.major}{sys.version_info.minor}.zip"
        )
        app_zip = tmp_path / "python_deps.zip"
        site_packages_app = Path(site_packages) / "my_app"
        site_packages_vendor_zip = Path(site_packages) / "vendor.zip"
        workspace.sys_path = ["/app"]
        workspace.environment["PYTHONPATH"] = os.pathsep.join(
            [
                stdlib,
                site_packages,
                str(stdlib_zip),
                str(app_zip),
                str(site_packages_app),
                str(site_packages_vendor_zip),
                "/extra",
            ]
        )

        env = workspace_environment(workspace)
        pythonpath_entries = env["PYTHONPATH"].split(os.pathsep)

        resolved_stdlib = str(Path(stdlib).resolve())
        resolved_site_packages = str(Path(site_packages).resolve())
        resolved_site_packages_app = str(site_packages_app.resolve())
        resolved_site_packages_vendor_zip = str(site_packages_vendor_zip.resolve())
        resolved_stdlib_zip = str(stdlib_zip.resolve())
        assert resolved_stdlib not in pythonpath_entries
        assert resolved_site_packages not in pythonpath_entries
        assert resolved_stdlib_zip not in pythonpath_entries
        assert str(app_zip) in pythonpath_entries
        assert resolved_site_packages_app in pythonpath_entries
        assert resolved_site_packages_vendor_zip in pythonpath_entries
        assert "/extra" in pythonpath_entries
