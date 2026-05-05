from __future__ import annotations

import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Iterator
from uuid import UUID

import anyio
import anyio.abc
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from prefect._internal.compatibility.backports import tomllib
from prefect.exceptions import MissingFlowError
from prefect.flows import load_flow_from_entrypoint, load_function_and_convert_to_flow
from prefect.runner._process_manager import ProcessHandle
from prefect.runner._starter_engine import EngineCommandStarter
from prefect.runner._workspace_resolver import (
    PreparedWorkspace,
    PreparedWorkspaceResult,
    get_workspace_resolver_command,
)
from prefect.settings import get_current_settings
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.processutils import command_to_string, sanitize_subprocess_env

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
    from prefect.flows import Flow
    from prefect.runner._control_channel import ControlChannel


def _decode_process_output(output: bytes | str | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return output


def _format_workspace_error(result: PreparedWorkspaceResult) -> str:
    if result.error is None:
        return "Workspace resolver failed without a structured error payload."

    message = f"{result.error.error_type}: {result.error.error_message}"
    if result.error.cause_type:
        message += f" (caused by {result.error.cause_type}"
        if result.error.cause_message:
            message += f": {result.error.cause_message}"
        message += ")"
    return message


async def resolve_workspace_in_subprocess(
    flow_run_id: UUID | str, workspace_root: Path
) -> PreparedWorkspace:
    environment = {
        **os.environ,
        **get_current_settings().to_environment_variables(exclude_unset=True),
    }
    process = await anyio.run_process(
        get_workspace_resolver_command(flow_run_id, workspace_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=sanitize_subprocess_env(environment),
        check=False,
    )

    stderr = _decode_process_output(process.stderr)
    if stderr:
        sys.stderr.write(stderr)
        sys.stderr.flush()

    stdout = _decode_process_output(process.stdout)
    try:
        result = PreparedWorkspaceResult.model_validate_json(stdout)
    except ValueError as exc:
        raise RuntimeError(
            "Workspace resolver did not return a valid JSON payload."
        ) from exc

    if process.returncode != 0 or result.status == "error":
        raise RuntimeError(_format_workspace_error(result))

    if result.workspace is None:
        raise RuntimeError("Workspace resolver returned success without a workspace.")

    return result.workspace


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


def workspace_environment(workspace: PreparedWorkspace) -> dict[str, str]:
    environment = dict(workspace.environment)
    pythonpath_entries = _workspace_sys_path(workspace)
    existing_pythonpath = environment.get("PYTHONPATH")
    if existing_pythonpath:
        for entry in existing_pythonpath.split(os.pathsep):
            if entry and entry not in pythonpath_entries:
                pythonpath_entries.append(entry)

    environment["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    return environment


def _absolute_file_entrypoint(workspace: PreparedWorkspace) -> str:
    entrypoint = workspace.runtime_entrypoint
    if ":" not in entrypoint:
        return entrypoint

    path, object_name = entrypoint.rsplit(":", 1)
    if not path.endswith(".py"):
        return entrypoint

    entrypoint_path = Path(path).expanduser()
    if not entrypoint_path.is_absolute():
        entrypoint_path = workspace.working_directory / entrypoint_path
    return f"{entrypoint_path.resolve()}:{object_name}"


def _dependencies_include_prefect(dependencies: object) -> bool:
    if not isinstance(dependencies, Iterable) or isinstance(dependencies, (str, bytes)):
        return False

    for dependency in dependencies:
        if not isinstance(dependency, str):
            continue
        try:
            name = Requirement(dependency).name
        except InvalidRequirement:
            continue
        if canonicalize_name(name) == "prefect":
            return True
    return False


def _pyproject_declares_prefect_dependency(pyproject: Path) -> bool:
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return False

    project = data.get("project")
    if not isinstance(project, dict):
        return False

    return _dependencies_include_prefect(project.get("dependencies"))


def _uv_run_command(workspace: PreparedWorkspace) -> str | None:
    project_root = workspace.project_root
    if project_root is None:
        return None

    pyproject = project_root / "pyproject.toml"
    if not pyproject.is_file() or not _pyproject_declares_prefect_dependency(pyproject):
        return None

    workspace_path = workspace.environment.get("PATH")
    uv_executable = (
        shutil.which("uv", path=workspace_path)
        if workspace_path is not None
        else shutil.which("uv")
    )
    if uv_executable is None:
        return None

    return command_to_string(
        [
            uv_executable,
            "run",
            "--project",
            str(project_root),
            "-m",
            "prefect.flow_engine",
            workspace.runtime_entrypoint,
        ]
    )


def _workspace_command(
    workspace: PreparedWorkspace, explicit_command: str | None
) -> str | None:
    if explicit_command is not None:
        return explicit_command
    return _uv_run_command(workspace)


@contextmanager
def _prepared_workspace_context(workspace: PreparedWorkspace) -> Iterator[None]:
    original_environment = dict(os.environ)
    original_sys_path = list(sys.path)

    try:
        os.environ.clear()
        os.environ.update(workspace_environment(workspace))
        sys.path[:] = _workspace_sys_path(workspace)
        yield
    finally:
        os.environ.clear()
        os.environ.update(original_environment)
        sys.path[:] = original_sys_path


async def load_flow_from_prepared_workspace(
    workspace: PreparedWorkspace,
) -> "Flow[Any, Any]":
    entrypoint = _absolute_file_entrypoint(workspace)
    with _prepared_workspace_context(workspace):
        try:
            return await run_sync_in_worker_thread(
                load_flow_from_entrypoint,
                entrypoint,
                use_placeholder_flow=False,
            )
        except MissingFlowError:
            return await run_sync_in_worker_thread(
                load_function_and_convert_to_flow,
                entrypoint,
            )


class WorkspaceResolvingEngineCommandStarter:
    def __init__(
        self,
        *,
        workspace_root: Path,
        command: str | None = None,
        stream_output: bool = True,
        heartbeat_seconds: int | None = None,
        control_channel: ControlChannel | None = None,
    ) -> None:
        self._workspace_root = workspace_root
        self._command = command
        self._stream_output = stream_output
        self._heartbeat_seconds = heartbeat_seconds
        self._control_channel = control_channel
        self._workspace: PreparedWorkspace | None = None

    @property
    def workspace(self) -> PreparedWorkspace | None:
        return self._workspace

    async def _resolve_workspace(self, flow_run_id: UUID | str) -> PreparedWorkspace:
        if self._workspace is None:
            self._workspace = await resolve_workspace_in_subprocess(
                flow_run_id, self._workspace_root
            )
        return self._workspace

    async def start(
        self,
        flow_run: FlowRun,
        task_status: anyio.abc.TaskStatus[ProcessHandle] = anyio.TASK_STATUS_IGNORED,
    ) -> None:
        workspace = await self._resolve_workspace(flow_run.id)
        starter = EngineCommandStarter(
            command=_workspace_command(workspace, self._command),
            cwd=workspace.working_directory,
            env=workspace_environment(workspace),
            entrypoint=workspace.runtime_entrypoint,
            stream_output=self._stream_output,
            heartbeat_seconds=self._heartbeat_seconds,
            control_channel=self._control_channel,
        )
        await starter.start(flow_run, task_status=task_status)

    async def resolve_flow(self, flow_run: FlowRun) -> "Flow[Any, Any]":
        workspace = await self._resolve_workspace(flow_run.id)
        return await load_flow_from_prepared_workspace(workspace)
