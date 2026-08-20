from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast
from uuid import uuid4

import anyio

from prefect.client.schemas.objects import FlowRun, State
from prefect.exceptions import MissingFlowError
from prefect.flows import load_flow_from_entrypoint, load_function_and_convert_to_flow
from prefect.logging.loggers import flow_run_logger
from prefect.runner._hook_runner import _run_hooks
from prefect.runner._workspace_runtime import (
    PreparedWorkspaceManifest,
    read_model,
    write_private_model,
)
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.processutils import run_process, sanitize_subprocess_env

if TYPE_CHECKING:
    from prefect.flows import Flow


HookType = Literal["cancellation", "crashed"]


def _absolute_file_entrypoint(manifest: PreparedWorkspaceManifest) -> str:
    entrypoint = manifest.runtime_entrypoint
    if ":" not in entrypoint:
        return entrypoint

    path, object_name = entrypoint.rsplit(":", 1)
    if not path.endswith(".py"):
        return entrypoint

    entrypoint_path = Path(path).expanduser()
    if not entrypoint_path.is_absolute():
        entrypoint_path = manifest.working_directory / entrypoint_path
    return f"{entrypoint_path.resolve()}:{object_name}"


async def _load_flow(manifest: PreparedWorkspaceManifest) -> Flow[Any, Any]:
    entrypoint = _absolute_file_entrypoint(manifest)
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


async def execute_hook_subprocess(
    hook_type: HookType,
    manifest_path: Path,
    flow_run_path: Path,
    state_path: Path,
) -> None:
    manifest = read_model(manifest_path, PreparedWorkspaceManifest)
    flow_run = read_model(flow_run_path, FlowRun)
    state = read_model(state_path, State)
    flow = await _load_flow(manifest)
    hooks = (
        flow.on_cancellation_hooks
        if hook_type == "cancellation"
        else flow.on_crashed_hooks
    )
    await _run_hooks(hooks or [], flow_run, flow, state)


class WorkspaceHookRunner:
    """Runs hooks in the runtime selected for a prepared workspace."""

    def __init__(
        self,
        *,
        manifest_path: Path,
        stream_output: bool,
    ) -> None:
        self._manifest_path = manifest_path
        self._stream_output = stream_output

    async def run_cancellation_hooks(self, flow_run: FlowRun, state: State) -> None:
        if state.is_cancelling():
            await self._run("cancellation", flow_run, state)

    async def run_crashed_hooks(self, flow_run: FlowRun, state: State) -> None:
        if state.is_crashed():
            await self._run("crashed", flow_run, state)

    async def _run(self, hook_type: HookType, flow_run: FlowRun, state: State) -> None:
        flow_run_path = self._manifest_path.parent / f"flow-run-{uuid4()}.json"
        state_path = self._manifest_path.parent / f"state-{uuid4()}.json"
        try:
            manifest = read_model(self._manifest_path, PreparedWorkspaceManifest)
            write_private_model(flow_run_path, flow_run)
            write_private_model(state_path, state)
            command = [
                *manifest.hook_command_prefix,
                "-m",
                "prefect.runner._workspace_hook_runner",
                hook_type,
                str(self._manifest_path),
                str(flow_run_path),
                str(state_path),
            ]
            process = await run_process(
                command,
                cwd=manifest.working_directory,
                env=sanitize_subprocess_env(manifest.environment),
                stream_output=self._stream_output,
            )
            if process.returncode != 0:
                raise RuntimeError(
                    f"Hook subprocess exited with status code {process.returncode}."
                )
        except Exception:
            flow_run_logger(flow_run).warning(
                "Runner failed to retrieve flow to execute on_%s hooks for flow run %r.",
                hook_type,
                flow_run.id,
                exc_info=True,
            )
        finally:
            flow_run_path.unlink(missing_ok=True)
            state_path.unlink(missing_ok=True)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load a prepared flow and execute its runner-owned hooks."
    )
    parser.add_argument("hook_type", choices=("cancellation", "crashed"))
    parser.add_argument("manifest", type=Path)
    parser.add_argument("flow_run", type=Path)
    parser.add_argument("state", type=Path)
    return parser.parse_args(argv)


async def _main_async(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        await execute_hook_subprocess(
            cast(HookType, args.hook_type),
            args.manifest,
            args.flow_run,
            args.state,
        )
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    return anyio.run(_main_async, argv)


if __name__ == "__main__":
    raise SystemExit(main())
