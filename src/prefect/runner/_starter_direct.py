from __future__ import annotations

from typing import TYPE_CHECKING, Any

import anyio
import anyio.abc

from prefect.flow_engine import run_flow_in_subprocess
from prefect.runner._process_manager import ProcessHandle

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
    from prefect.flows import Flow


class DirectSubprocessStarter:
    """Runs a flow object directly in a subprocess via `run_flow_in_subprocess`.

    Source: runner.py lines 874-889.
    Uses module-level `run_flow_in_subprocess` reference -- patch the module
    to override.
    """

    def __init__(
        self,
        *,
        flow: Flow[Any, Any],
        heartbeat_seconds: int | None = None,
    ) -> None:
        self._flow = flow
        self._heartbeat_seconds = heartbeat_seconds

    async def start(
        self,
        flow_run: FlowRun,
        task_status: anyio.abc.TaskStatus[ProcessHandle] = anyio.TASK_STATUS_IGNORED,
    ) -> None:
        subprocess_env: dict[str, str] = {}
        if self._heartbeat_seconds is not None:
            subprocess_env["PREFECT_FLOWS_HEARTBEAT_FREQUENCY"] = str(
                int(self._heartbeat_seconds)
            )
        process = run_flow_in_subprocess(
            self._flow,
            flow_run=flow_run,
            env=subprocess_env or None,
        )
        handle = ProcessHandle(process)
        task_status.started(handle)  # signal BEFORE blocking join
        await anyio.to_thread.run_sync(process.join)  # SpawnProcess.join is sync
