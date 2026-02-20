import asyncio
import multiprocessing.context
import os
import signal
import sys
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import UUID

import anyio
import anyio.abc

from prefect.logging import get_logger


@dataclass
class ProcessHandle:
    _process: anyio.abc.Process | multiprocessing.context.SpawnProcess

    @property
    def pid(self) -> int | None:
        return self._process.pid

    @property
    def returncode(self) -> int | None:
        if hasattr(self._process, "returncode"):
            return self._process.returncode
        return getattr(self._process, "exitcode", None)

    @property
    def raw_process(self) -> anyio.abc.Process | multiprocessing.context.SpawnProcess:
        return self._process


class ProcessManager:
    def __init__(
        self,
        *,
        on_add: Callable[[UUID], Awaitable[None]] | None = None,
        on_remove: Callable[[UUID], Awaitable[None]] | None = None,
    ) -> None:
        self._logger = get_logger("runner.process_manager")
        self._process_map: dict[UUID, ProcessHandle] = {}
        self._lock: asyncio.Lock | None = None
        self._on_add = on_add
        self._on_remove = on_remove

    @property
    def _process_map_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def __aenter__(self) -> "ProcessManager":
        self._lock = asyncio.Lock()
        return self

    async def __aexit__(self, *_: Any) -> None:
        async with self._process_map_lock:
            flow_run_ids = list(self._process_map.keys())

        for flow_run_id in flow_run_ids:
            try:
                await self.kill(flow_run_id)
            except Exception:
                self._logger.error(
                    "Failed to kill process for flow run '%s' during shutdown.",
                    flow_run_id,
                    exc_info=True,
                )

        async with self._process_map_lock:
            self._process_map.clear()

    async def add(self, flow_run_id: UUID, handle: ProcessHandle) -> None:
        async with self._process_map_lock:
            self._process_map[flow_run_id] = handle

        if self._on_add is not None:
            try:
                await self._on_add(flow_run_id)
            except Exception:
                self._logger.error(
                    "on_add callback raised for flow run '%s'",
                    flow_run_id,
                    exc_info=True,
                )

    async def remove(self, flow_run_id: UUID) -> None:
        async with self._process_map_lock:
            self._process_map.pop(flow_run_id, None)

        if self._on_remove is not None:
            try:
                await self._on_remove(flow_run_id)
            except Exception:
                self._logger.error(
                    "on_remove callback raised for flow run '%s'",
                    flow_run_id,
                    exc_info=True,
                )

    def get(self, flow_run_id: UUID) -> ProcessHandle | None:
        return self._process_map.get(flow_run_id)

    async def kill(self, flow_run_id: UUID, grace_seconds: int = 30) -> None:
        handle = self._process_map.get(flow_run_id)
        if handle is None:
            self._logger.warning(
                "Received kill request for flow run '%s' but no process was found.",
                flow_run_id,
            )
            return

        pid = handle.pid
        if pid is None:
            self._logger.warning(
                "Process for flow run '%s' has no PID.",
                flow_run_id,
            )
            return

        if sys.platform == "win32":
            os.kill(pid, signal.CTRL_BREAK_EVENT)
        else:
            os.kill(pid, signal.SIGTERM)

            check_interval = max(grace_seconds / 10, 1)
            with anyio.move_on_after(grace_seconds):
                while True:
                    await anyio.sleep(check_interval)
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        return
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                return
