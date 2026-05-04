from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import anyio
import anyio.abc

from prefect.bundles import execute_bundle_in_subprocess
from prefect.runner._process_manager import ProcessHandle

if TYPE_CHECKING:
    from prefect.bundles import SerializedBundle
    from prefect.client.schemas.objects import FlowRun
    from prefect.runner._control_channel import ControlChannel


class BundleExecutionStarter:
    """Executes a pre-serialized bundle in a subprocess via `SpawnProcess`.

    Source: runner.py lines 771-841.
    Uses module-level `execute_bundle_in_subprocess` reference -- patch the
    module to override.

    CRITICAL: `SpawnProcess.join()` is synchronous (multiprocessing). Must use
    `await anyio.to_thread.run_sync(process.join)` to avoid blocking the event
    loop.
    """

    def __init__(
        self,
        *,
        bundle: SerializedBundle,
        cwd: Path | None = None,
        env: dict[str, str | None] | None = None,
        control_channel: ControlChannel | None = None,
    ) -> None:
        self._bundle = bundle
        self._cwd = cwd
        self._env = env or {}
        self._control_channel = control_channel

    async def start(
        self,
        flow_run: FlowRun,
        task_status: anyio.abc.TaskStatus[ProcessHandle] = anyio.TASK_STATUS_IGNORED,
    ) -> None:
        env: dict[str, str | None] = {**self._env}
        control_registered = False
        if self._control_channel is not None:
            try:
                port, token = self._control_channel.register(flow_run.id)
                env["PREFECT__CONTROL_PORT"] = str(port)
                env["PREFECT__CONTROL_TOKEN"] = token
                control_registered = True
            except RuntimeError:
                # The channel may be disabled if the runner could not bind a
                # loopback listener. In that case we silently fall back to the
                # legacy kill-only cancellation path.
                pass
        handed_off = False
        try:
            process = execute_bundle_in_subprocess(
                self._bundle,
                cwd=self._cwd,
                env=env or None,
            )
            handle = ProcessHandle(process)
            task_status.started(handle)  # signal BEFORE blocking join
            handed_off = True
            await anyio.to_thread.run_sync(process.join)  # SpawnProcess.join is sync
        except BaseException:
            if control_registered and not handed_off:
                self._control_channel.unregister(flow_run.id)
            raise
