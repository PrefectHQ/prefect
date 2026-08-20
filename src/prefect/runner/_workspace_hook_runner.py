from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import uuid4

from prefect.client.schemas.objects import FlowRun, State
from prefect.logging.loggers import flow_run_logger
from prefect.runner._workspace_runtime import (
    PreparedWorkspaceManifest,
    read_model,
    write_private_model,
)
from prefect.utilities.processutils import run_process, sanitize_subprocess_env

HookType = Literal["cancellation", "crashed"]


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
            if manifest.hook_command is None:
                flow_run_logger(flow_run).warning(
                    "Runner cannot execute on_%s hooks for flow run %r because the "
                    "configured flow-run command does not expose a Python runtime.",
                    hook_type,
                    flow_run.id,
                )
                return
            write_private_model(flow_run_path, flow_run)
            write_private_model(state_path, state)
            command = [
                *manifest.hook_command,
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
