from __future__ import annotations

from typing import TYPE_CHECKING, Any

import anyio
import anyio.abc

from prefect.flow_engine import run_flow_in_subprocess
from prefect.runner._process_manager import ProcessHandle

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
    from prefect.flows import Flow
    from prefect.runner._control_channel import ControlChannel


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
        control_channel: ControlChannel | None = None,
    ) -> None:
        self._flow = flow
        self._heartbeat_seconds = heartbeat_seconds
        self._control_channel = control_channel

    async def start(
        self,
        flow_run: FlowRun,
        task_status: anyio.abc.TaskStatus[ProcessHandle] = anyio.TASK_STATUS_IGNORED,
    ) -> None:
        subprocess_env: dict[str, str] = {}
        control_registered = False
        if self._heartbeat_seconds is not None:
            subprocess_env["PREFECT_FLOWS_HEARTBEAT_FREQUENCY"] = str(
                int(self._heartbeat_seconds)
            )
        if self._control_channel is not None:
            try:
                port, token = self._control_channel.register(flow_run.id)
                subprocess_env["PREFECT__CONTROL_PORT"] = str(port)
                subprocess_env["PREFECT__CONTROL_TOKEN"] = token
                control_registered = True
            except RuntimeError:
                # The channel may be disabled if the runner could not bind a
                # loopback listener. In that case we silently fall back to the
                # legacy kill-only cancellation path.
                pass
        handed_off = False
        try:
            process = run_flow_in_subprocess(
                self._flow,
                flow_run=flow_run,
                env=subprocess_env or None,
            )
            handle = ProcessHandle(process)
            task_status.started(handle)  # signal BEFORE blocking join
            handed_off = True
            await anyio.to_thread.run_sync(process.join)  # SpawnProcess.join is sync
        except BaseException:
            if control_registered and not handed_off:
                self._control_channel.unregister(flow_run.id)
            raise
