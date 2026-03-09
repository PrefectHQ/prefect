from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import anyio
import anyio.abc

from prefect._experimental.bundles import execute_bundle_in_subprocess
from prefect.runner._process_manager import ProcessHandle

if TYPE_CHECKING:
    from prefect._experimental.bundles import SerializedBundle
    from prefect.client.schemas.objects import FlowRun


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
    ) -> None:
        self._bundle = bundle
        self._cwd = cwd
        self._env = env or {}

    async def start(
        self,
        flow_run: FlowRun,
        task_status: anyio.abc.TaskStatus[ProcessHandle] = anyio.TASK_STATUS_IGNORED,
    ) -> None:
        process = execute_bundle_in_subprocess(
            self._bundle,
            cwd=self._cwd,
            env=self._env or None,
        )
        handle = ProcessHandle(process)
        task_status.started(handle)  # signal BEFORE blocking join
        await anyio.to_thread.run_sync(process.join)  # SpawnProcess.join is sync
