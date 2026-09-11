from __future__ import annotations

import functools
import os
import site
import sys
import sysconfig
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

import anyio
import anyio.abc
from pydantic import TypeAdapter, ValidationError

from prefect.runner._process_manager import ProcessHandle
from prefect.runner._starter_engine import EngineCommandStarter
from prefect.runner._uv_command import uv_project_command
from prefect.runner._workspace_hook_runner import WorkspaceHookRunner
from prefect.runner._workspace_resolver import PreparedWorkspace
from prefect.runner._workspace_runtime import (
    WorkspaceSupervisorConfig,
    write_private_model,
)
from prefect.utilities.processutils import command_to_string, get_sys_executable

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
    from prefect.runner._control_channel import ControlChannel


def _workspace_sys_path(workspace: PreparedWorkspace) -> list[str]:
    entries: list[str] = []
    for entry in [str(workspace.working_directory), *workspace.sys_path]:
        if not entry:
            resolved_entry = str(workspace.working_directory)
        else:
            path = Path(entry).expanduser()
            if path.is_absolute():
                resolved_entry = str(path)
            else:
                resolved_entry = str((workspace.working_directory / path).resolve())

        if resolved_entry not in entries:
            entries.append(resolved_entry)
    return entries


@functools.lru_cache(maxsize=1)
def _stdlib_prefixes() -> tuple[str, ...]:
    """Resolved stdlib directory prefixes whose children should not land on PYTHONPATH."""
    roots: set[str] = set()
    paths = sysconfig.get_paths()
    for key in ("stdlib", "platstdlib"):
        val = paths.get(key)
        if val:
            roots.add(str(Path(val).resolve()))
    return tuple(sorted(roots))


@functools.lru_cache(maxsize=1)
def _site_packages_dirs() -> tuple[str, ...]:
    """Resolved site-packages directories that should not be promoted to PYTHONPATH."""
    dirs: set[str] = set()
    paths = sysconfig.get_paths()
    for key in ("purelib", "platlib"):
        val = paths.get(key)
        if val:
            dirs.add(str(Path(val).resolve()))
    try:
        for sp in site.getsitepackages():
            dirs.add(str(Path(sp).resolve()))
    except AttributeError:
        pass
    try:
        usp = site.getusersitepackages()
        if isinstance(usp, str):
            dirs.add(str(Path(usp).resolve()))
    except AttributeError:
        pass
    return tuple(sorted(dirs))


def _is_interpreter_path(entry: str) -> bool:
    """True when *entry* is managed by the interpreter rather than the workspace.

    The interpreter already adds stdlib, lib-dynload, and site-packages directories
    in the correct order. Adding any of them to PYTHONPATH changes that ordering and
    can let a site-packages backport shadow a standard-library module. Only
    interpreter stdlib zip archives next to stdlib directories are filtered; user
    archives like `/app/python_deps.zip` are preserved.
    """
    if not entry:
        return False

    resolved_path = Path(entry).resolve()
    resolved = str(resolved_path)

    site_packages_dirs = _site_packages_dirs()
    if resolved in site_packages_dirs:
        return True
    if any(resolved.startswith(sp + os.sep) for sp in site_packages_dirs):
        return False

    for root in _stdlib_prefixes():
        if resolved == root or resolved.startswith(root + os.sep):
            return True

    interpreter_zip_name = f"python{sys.version_info.major}{sys.version_info.minor}.zip"
    if resolved_path.name == interpreter_zip_name:
        resolved_parent = str(resolved_path.parent)
        stdlib_parents = {str(Path(r).parent) for r in _stdlib_prefixes()}
        if resolved_parent in stdlib_parents:
            return True

    return False


def workspace_environment(workspace: PreparedWorkspace) -> dict[str, str]:
    environment = dict(workspace.environment)
    pythonpath_entries: list[str] = []
    candidate_entries = _workspace_sys_path(workspace)
    existing_pythonpath = environment.get("PYTHONPATH")
    if existing_pythonpath:
        candidate_entries.extend(existing_pythonpath.split(os.pathsep))

    for entry in candidate_entries:
        if (
            entry
            and entry not in pythonpath_entries
            and not _is_interpreter_path(entry)
        ):
            pythonpath_entries.append(entry)

    environment["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    return environment


def _uv_run_command(
    workspace: PreparedWorkspace, environment: Mapping[str, str]
) -> str | None:
    auto_install = environment.get("PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES")
    try:
        auto_install_dependencies = (
            TypeAdapter(bool).validate_python(auto_install)
            if auto_install is not None
            else None
        )
    except ValidationError:
        auto_install_dependencies = None

    return uv_project_command(
        workspace.project_root,
        [
            str(Path(__file__).with_name("_workspace_runtime_bootstrap.py")),
            "engine",
            workspace.runtime_entrypoint,
        ],
        path=environment.get("PATH"),
        auto_install_dependencies=auto_install_dependencies,
    )


def _workspace_command(
    workspace: PreparedWorkspace,
    explicit_command: str | None,
    *,
    environment: Mapping[str, str],
) -> str | None:
    if explicit_command is not None:
        return explicit_command
    return _uv_run_command(workspace, environment)


class WorkspaceResolvingEngineCommandStarter:
    def __init__(
        self,
        *,
        workspace_root: Path,
        command: str | None = None,
        stream_output: bool = True,
        heartbeat_seconds: int | None = None,
        deployment_name: str | None = None,
        control_channel: ControlChannel | None = None,
        source_cwd: Path | str | None = None,
        environment: Mapping[str, str | None] | None = None,
    ) -> None:
        self._workspace_root = workspace_root
        self._command = command
        self._stream_output = stream_output
        self._heartbeat_seconds = heartbeat_seconds
        self._deployment_name = deployment_name
        self._control_channel = control_channel
        self._source_cwd = source_cwd
        self._environment = dict(environment or {})
        self._runtime_directory = tempfile.TemporaryDirectory(
            prefix="prefect-workspace-attempt-"
        )
        runtime_root = Path(self._runtime_directory.name)
        self._config_path = runtime_root / "supervisor.json"
        self._manifest_path = runtime_root / "workspace.json"
        self._hook_runner = WorkspaceHookRunner(
            manifest_path=self._manifest_path,
            stream_output=self._stream_output,
        )

    @property
    def hook_runner(self) -> WorkspaceHookRunner:
        return self._hook_runner

    def close(self) -> None:
        self._runtime_directory.cleanup()

    async def start(
        self,
        flow_run: FlowRun,
        task_status: anyio.abc.TaskStatus[ProcessHandle] = anyio.TASK_STATUS_IGNORED,
    ) -> None:
        write_private_model(
            self._config_path,
            WorkspaceSupervisorConfig(
                flow_run_id=flow_run.id,
                workspace_root=self._workspace_root,
                manifest_path=self._manifest_path,
                command=self._command,
            ),
        )
        supervisor_command = command_to_string(
            [
                get_sys_executable(),
                "-m",
                "prefect.runner._workspace_supervisor",
                str(self._config_path),
            ]
        )
        starter = EngineCommandStarter(
            command=supervisor_command,
            cwd=self._source_cwd,
            env=self._environment,
            stream_output=self._stream_output,
            heartbeat_seconds=self._heartbeat_seconds,
            deployment_name=self._deployment_name,
            control_channel=self._control_channel,
            # The Windows supervisor joins its own Job Object before preparation;
            # assigning it from this post-spawn callback would leave a race.
            isolate_process_group=sys.platform != "win32",
            env_overrides_settings=True,
        )
        await starter.start(flow_run, task_status=task_status)
