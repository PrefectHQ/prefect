from __future__ import annotations

import argparse
import builtins
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
from prefect.deployments.steps.core import _observe_step_completion, run_steps
from prefect.filesystems import LocalFileSystem
from prefect.logging.loggers import get_logger
from prefect.utilities.filesystem import relative_path_to_current_platform
from prefect.utilities.processutils import get_sys_executable

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import FlowRun
    from prefect.client.schemas.responses import DeploymentResponse

LOGGER = get_logger("prefect.runner.workspace_resolver")


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


def _stderr_print(*args: Any, **kwargs: Any) -> None:
    kwargs.pop("style", None)
    builtins.print(*args, file=sys.stderr, **kwargs)


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


def _resolve_local_deployment_path(
    path: str | None, workspace_root: Path, source_cwd: Path
) -> str | None:
    if path is None:
        return None

    path = path.replace("$STORAGE_BASE_PATH", str(workspace_root))
    resolved_path = Path(path).expanduser()
    if resolved_path.is_absolute():
        return str(resolved_path.resolve())
    return str((source_cwd / resolved_path).resolve())


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
) -> None:
    if deployment.storage_document_id:
        storage_document = await client.read_block_document(
            deployment.storage_document_id
        )
        from prefect.blocks.core import Block

        storage_block = Block._from_block_document(storage_document)
        from_path = (
            str(deployment.path).replace("$STORAGE_BASE_PATH", str(workspace_root))
            if deployment.path
            else None
        )
    else:
        from_path = _resolve_local_deployment_path(
            deployment.path, workspace_root, source_cwd
        )
        storage_block = LocalFileSystem(basepath=from_path)

    LOGGER.info("Downloading flow code from storage at %r", from_path)
    await storage_block.get_directory(
        from_path=from_path, local_path=str(workspace_root)
    )


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

    source_cwd = Path.cwd().resolve()
    resolved_workspace_root = Path(workspace_root).expanduser().resolve()
    resolved_workspace_root.mkdir(parents=True, exist_ok=True)
    working_directory = resolved_workspace_root

    if not deployment.pull_steps:
        await _pull_storage_into_workspace(
            client, deployment, resolved_workspace_root, source_cwd
        )
        os.chdir(resolved_workspace_root)
        working_directory = Path.cwd().resolve()
    else:
        os.chdir(resolved_workspace_root)
        working_directory = Path.cwd().resolve()
        LOGGER.info("Running %s deployment pull step(s)", len(deployment.pull_steps))

        def _track_step_workspace(
            _step: dict[str, Any],
            step_output: Any,
            step_start_cwd: Path | None,
            step_end_cwd: Path | None,
        ) -> None:
            nonlocal working_directory

            if isinstance(step_output, dict) and "directory" in step_output:
                resolved_directory = _resolve_directory_output(
                    step_output, step_end_cwd
                )
                if resolved_directory is not None:
                    working_directory = resolved_directory
                return

            if step_end_cwd is not None and step_end_cwd != step_start_cwd:
                working_directory = step_end_cwd

        with _observe_step_completion(_track_step_workspace):
            await run_steps(
                deployment.pull_steps,
                print_function=_stderr_print,
                deployment=deployment,
                flow_run=flow_run,
                logger=LOGGER,
            )

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

    result = PreparedWorkspaceResult(status="success", workspace=workspace)
    sys.stdout.write(result.model_dump_json())
    sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    return anyio.run(_main_async, argv)


if __name__ == "__main__":
    raise SystemExit(main())
