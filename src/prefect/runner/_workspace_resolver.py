from __future__ import annotations

import argparse
import contextlib
import os
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

import anyio
from pydantic import BaseModel

from prefect.client.orchestration import get_client
from prefect.deployments.steps.core import (
    _PULL_STEP_SOURCE_CWD,
    _observe_step_completion,
    run_steps,
)
from prefect.filesystems import LocalFileSystem
from prefect.logging.handlers import APILogHandler
from prefect.logging.loggers import PrefectLogAdapter, flow_run_logger
from prefect.utilities.filesystem import relative_path_to_current_platform
from prefect.utilities.processutils import get_sys_executable

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import FlowRun
    from prefect.client.schemas.responses import DeploymentResponse

STORAGE_BASE_PATH_PLACEHOLDER = "$STORAGE_BASE_PATH"


class PreparedWorkspace(BaseModel):
    workspace_root: Path
    working_directory: Path
    project_root: Path | None = None
    runtime_entrypoint: str
    environment: dict[str, str]
    sys_path: list[str]


class PreparedWorkspaceError(BaseModel):
    error_type: str
    error_message: str
    cause_type: str | None = None
    cause_message: str | None = None


class PreparedWorkspaceResult(BaseModel):
    status: Literal["success", "error"]
    workspace: PreparedWorkspace | None = None
    error: PreparedWorkspaceError | None = None


def get_workspace_resolver_command(
    flow_run_id: UUID | str, workspace_root: Path | str
) -> list[str]:
    return [
        get_sys_executable(),
        "-m",
        "prefect.runner._workspace_resolver",
        str(flow_run_id),
        str(workspace_root),
    ]


def _resolve_runtime_entrypoint(entrypoint: str) -> str:
    if ":" not in entrypoint:
        return entrypoint
    return str(relative_path_to_current_platform(entrypoint))


def _resolve_directory_output(
    step_output: dict[str, Any], step_end_cwd: Path | None
) -> Path | None:
    directory = step_output.get("directory")
    candidate = Path(directory).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    if step_end_cwd is None:
        return None
    return (step_end_cwd / candidate).resolve()


def _find_nearest_pyproject_ancestor(start: Path, lower_bound: Path) -> Path | None:
    current = start.resolve()
    boundary = lower_bound.resolve()

    while True:
        if (current / "pyproject.toml").is_file():
            return current
        if current == boundary:
            return None
        current = current.parent


def _find_project_root(working_directory: Path, workspace_root: Path) -> Path | None:
    resolved_working_directory = working_directory.resolve()
    resolved_workspace_root = workspace_root.resolve()

    try:
        resolved_working_directory.relative_to(resolved_workspace_root)
    except ValueError:
        return _find_nearest_pyproject_ancestor(
            resolved_working_directory,
            Path(resolved_working_directory.anchor),
        )

    return _find_nearest_pyproject_ancestor(
        resolved_working_directory,
        resolved_workspace_root,
    )


def _capture_environment() -> dict[str, str]:
    return dict(os.environ)


def _capture_sys_path() -> list[str]:
    return [str(path_entry) for path_entry in sys.path]


def _get_configured_storage_base_path() -> Path | None:
    storage_base_path = os.environ.get("PREFECT__STORAGE_BASE_PATH")
    if not storage_base_path:
        return None
    return Path(storage_base_path).expanduser().resolve()


def _substitute_storage_base_path(path: str, storage_base_path: Path | None) -> str:
    if storage_base_path is None:
        return path
    return path.replace(STORAGE_BASE_PATH_PLACEHOLDER, str(storage_base_path))


def _resolve_local_deployment_path(
    path: str | None, source_cwd: Path, storage_base_path: Path | None
) -> str | None:
    if path is None:
        return None

    path = _substitute_storage_base_path(path, storage_base_path)
    resolved_path = Path(path).expanduser()
    if resolved_path.is_absolute():
        return str(resolved_path.resolve())
    return str((source_cwd / resolved_path).resolve())


def _workspace_destination_for_deployment_path(
    path: str | None, workspace_root: Path, storage_base_path: Path | None
) -> Path:
    if (
        path is None
        or storage_base_path is None
        or STORAGE_BASE_PATH_PLACEHOLDER not in path
    ):
        return workspace_root

    source_path = Path(
        path.replace(STORAGE_BASE_PATH_PLACEHOLDER, str(storage_base_path))
    ).expanduser()
    if not source_path.is_absolute():
        return workspace_root

    try:
        relative_destination = source_path.resolve().relative_to(storage_base_path)
    except ValueError:
        return workspace_root

    return (workspace_root / relative_destination).resolve()


def _resolve_local_runtime_directory(
    path: str | None, source_cwd: Path, storage_base_path: Path | None
) -> Path:
    resolved_path = _resolve_local_deployment_path(path, source_cwd, storage_base_path)
    return Path(resolved_path).resolve() if resolved_path is not None else source_cwd


def _entrypoint_file_path(entrypoint: str, working_directory: Path) -> Path | None:
    entrypoint = _resolve_runtime_entrypoint(entrypoint)
    if ":" not in entrypoint:
        return None

    path, _object_name = entrypoint.rsplit(":", 1)
    if not path.endswith(".py"):
        return None

    entrypoint_path = Path(path).expanduser()
    if not entrypoint_path.is_absolute():
        entrypoint_path = working_directory / entrypoint_path
    return entrypoint_path.resolve()


def _has_entrypoint_file(entrypoint: str, working_directory: Path) -> bool:
    entrypoint_path = _entrypoint_file_path(entrypoint, working_directory)
    return entrypoint_path is not None and entrypoint_path.is_file()


async def _ensure_entrypoint_in_workspace(
    client: "PrefectClient",
    deployment: "DeploymentResponse",
    workspace_root: Path,
    source_cwd: Path,
    storage_base_path: Path | None,
    logger: PrefectLogAdapter,
) -> Path:
    if _has_entrypoint_file(deployment.entrypoint, workspace_root):
        return workspace_root

    local_runtime_directory = _resolve_local_runtime_directory(
        deployment.path, source_cwd, storage_base_path
    )
    if not deployment.storage_document_id and not _has_entrypoint_file(
        deployment.entrypoint, local_runtime_directory
    ):
        return workspace_root

    await _pull_storage_into_workspace(
        client,
        deployment,
        workspace_root,
        source_cwd,
        storage_base_path,
        logger,
    )
    return workspace_root


@contextlib.contextmanager
def _redirect_stdout_to_stderr() -> Any:
    stdout = sys.stdout
    stderr = sys.stderr

    stdout.flush()
    stderr.flush()

    saved_stdout_fd = os.dup(stdout.fileno())
    try:
        os.dup2(stderr.fileno(), stdout.fileno())
        with contextlib.redirect_stdout(stderr):
            yield
            stderr.flush()
    finally:
        stdout.flush()
        os.dup2(saved_stdout_fd, stdout.fileno())
        os.close(saved_stdout_fd)


async def _pull_storage_into_workspace(
    client: "PrefectClient",
    deployment: "DeploymentResponse",
    workspace_root: Path,
    source_cwd: Path,
    storage_base_path: Path | None,
    logger: PrefectLogAdapter,
) -> Path:
    local_path = _workspace_destination_for_deployment_path(
        deployment.path, workspace_root, storage_base_path
    )

    if deployment.storage_document_id:
        storage_document = await client.read_block_document(
            deployment.storage_document_id
        )
        from prefect.blocks.core import Block

        storage_block = Block._from_block_document(storage_document)
        from_path = (
            _substitute_storage_base_path(str(deployment.path), storage_base_path)
            if deployment.path
            else None
        )
    else:
        resolved_local_path = _resolve_local_deployment_path(
            deployment.path, source_cwd, storage_base_path
        )
        from_path = (
            resolved_local_path if resolved_local_path is not None else str(source_cwd)
        )
        storage_block = LocalFileSystem(basepath=from_path)

    logger.info("Downloading flow code from storage at %r", from_path)
    await storage_block.get_directory(from_path=from_path, local_path=str(local_path))
    return local_path


async def prepare_workspace(
    client: "PrefectClient",
    flow_run: "FlowRun",
    deployment: "DeploymentResponse",
    workspace_root: Path | str,
) -> PreparedWorkspace:
    if deployment.entrypoint is None:
        raise ValueError(
            f"Deployment {deployment.id} does not have an entrypoint and can not be run."
        )

    run_logger = flow_run_logger(flow_run)

    source_cwd = Path.cwd().resolve()
    storage_base_path = _get_configured_storage_base_path()
    resolved_workspace_root = Path(workspace_root).expanduser().resolve()
    resolved_workspace_root.mkdir(parents=True, exist_ok=True)
    working_directory = resolved_workspace_root

    if not deployment.pull_steps:
        working_directory = await _pull_storage_into_workspace(
            client,
            deployment,
            resolved_workspace_root,
            source_cwd,
            storage_base_path,
            run_logger,
        )
        local_runtime_directory = _resolve_local_runtime_directory(
            deployment.path, source_cwd, storage_base_path
        )
        if not _has_entrypoint_file(
            deployment.entrypoint, working_directory
        ) and _has_entrypoint_file(deployment.entrypoint, local_runtime_directory):
            working_directory = local_runtime_directory
    else:
        working_directory = resolved_workspace_root
        step_selected_working_directory = False
        os.chdir(resolved_workspace_root)
        run_logger.info(
            "Running %s deployment pull step(s)", len(deployment.pull_steps)
        )

        def _track_step_workspace(
            _step: dict[str, Any],
            step_output: Any,
            step_start_cwd: Path | None,
            step_end_cwd: Path | None,
        ) -> None:
            nonlocal step_selected_working_directory, working_directory

            if isinstance(step_output, dict) and step_output.get("directory"):
                resolved_directory = _resolve_directory_output(
                    step_output, step_end_cwd
                )
                if resolved_directory is not None:
                    step_selected_working_directory = True
                    working_directory = resolved_directory
            elif step_end_cwd is not None and step_end_cwd != step_start_cwd:
                step_selected_working_directory = True
                working_directory = step_end_cwd

            # Clear source CWD after every step so the fallback only applies
            # to the first pull step (the baked-image case).  Steps that run
            # before set_working_directory (e.g. run_shell_script) create
            # workspace-relative content, so subsequent relative paths must
            # resolve against the current CWD, not the original process CWD.
            _PULL_STEP_SOURCE_CWD.set(None)

        source_cwd_token = _PULL_STEP_SOURCE_CWD.set(source_cwd)
        try:
            with _observe_step_completion(_track_step_workspace):
                await run_steps(
                    deployment.pull_steps,
                    print_function=run_logger.info,
                    deployment=deployment,
                    flow_run=flow_run,
                    logger=run_logger,
                )
        finally:
            _PULL_STEP_SOURCE_CWD.reset(source_cwd_token)

        if not step_selected_working_directory:
            working_directory = await _ensure_entrypoint_in_workspace(
                client,
                deployment,
                resolved_workspace_root,
                source_cwd,
                storage_base_path,
                run_logger,
            )

    os.chdir(working_directory)
    working_directory = Path.cwd().resolve()

    project_root = _find_project_root(working_directory, resolved_workspace_root)
    return PreparedWorkspace(
        workspace_root=resolved_workspace_root,
        working_directory=working_directory,
        project_root=project_root,
        runtime_entrypoint=_resolve_runtime_entrypoint(deployment.entrypoint),
        environment=_capture_environment(),
        sys_path=_capture_sys_path(),
    )


async def prepare_workspace_for_flow_run(
    flow_run_id: UUID | str,
    workspace_root: Path | str,
) -> PreparedWorkspace:
    async with get_client() as client:
        flow_run = await client.read_flow_run(UUID(str(flow_run_id)))
        if flow_run.deployment_id is None:
            raise ValueError("Flow run does not have an associated deployment")

        deployment = await client.read_deployment(flow_run.deployment_id)
        return await prepare_workspace(client, flow_run, deployment, workspace_root)


def _build_error(exc: BaseException) -> PreparedWorkspaceError:
    cause = exc.__cause__
    return PreparedWorkspaceError(
        error_type=type(exc).__name__,
        error_message=str(exc),
        cause_type=type(cause).__name__ if cause else None,
        cause_message=str(cause) if cause else None,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a flow run workspace in an isolated subprocess."
    )
    parser.add_argument("flow_run_id", type=UUID)
    parser.add_argument("workspace_root")
    return parser.parse_args(argv)


async def _main_async(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        with _redirect_stdout_to_stderr():
            workspace = await prepare_workspace_for_flow_run(
                args.flow_run_id, args.workspace_root
            )
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        result = PreparedWorkspaceResult(status="error", error=_build_error(exc))
        sys.stdout.write(result.model_dump_json())
        sys.stdout.write("\n")
        return 1
    finally:
        await APILogHandler.aflush()

    result = PreparedWorkspaceResult(status="success", workspace=workspace)
    sys.stdout.write(result.model_dump_json())
    sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    return anyio.run(_main_async, argv)


if __name__ == "__main__":
    raise SystemExit(main())
