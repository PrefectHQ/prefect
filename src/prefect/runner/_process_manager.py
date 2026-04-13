import asyncio
import ctypes
import multiprocessing.context
import os
import signal
import sys
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import UUID

import anyio
import anyio.abc

from prefect.logging import get_logger

_WINDOWS_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_WINDOWS_SYNCHRONIZE = 0x00100000
_WINDOWS_PROCESS_PROBE_ACCESS = (
    _WINDOWS_PROCESS_QUERY_LIMITED_INFORMATION | _WINDOWS_SYNCHRONIZE
)
_WINDOWS_WAIT_OBJECT_0 = 0x00000000
_WINDOWS_WAIT_TIMEOUT = 0x00000102
_windows_kernel32: ctypes.WinDLL | None = None


def _get_windows_kernel32() -> ctypes.WinDLL:
    global _windows_kernel32

    if _windows_kernel32 is None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.WaitForSingleObject.restype = ctypes.c_uint32
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        _windows_kernel32 = kernel32

    return _windows_kernel32


def _pid_is_alive(pid: int) -> bool:
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        else:
            return True

    kernel32 = _get_windows_kernel32()
    handle = kernel32.OpenProcess(_WINDOWS_PROCESS_PROBE_ACCESS, False, pid)
    if not handle:
        return False

    try:
        wait_result = kernel32.WaitForSingleObject(handle, 0)
        if wait_result == _WINDOWS_WAIT_TIMEOUT:
            return True
        if wait_result == _WINDOWS_WAIT_OBJECT_0:
            return False
        return True
    finally:
        kernel32.CloseHandle(handle)


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

    def flow_run_ids(self) -> set[UUID]:
        """Return a snapshot copy of currently tracked flow run IDs.

        Returns a copy to prevent RuntimeError when cancel_all iterates
        while cancel() calls remove() concurrently.
        """
        return set(self._process_map.keys())

    async def wait_for_exit(self, flow_run_id: UUID, grace_seconds: float = 30) -> bool:
        """Wait for a tracked process to exit without sending a signal.

        Returns `True` if the process exited (or was already gone) within the
        grace period, `False` if it remained alive through the timeout.
        """
        deadline = time.monotonic() + max(grace_seconds, 0)
        check_interval = max(grace_seconds / 10, 1) if grace_seconds > 0 else 0

        while True:
            handle = self.get(flow_run_id)
            if handle is None:
                return True

            if handle.returncode is not None:
                return True

            pid = handle.pid
            if pid is None:
                return True

            if not _pid_is_alive(pid):
                return True

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False

            await anyio.sleep(min(check_interval, remaining))

    async def kill(self, flow_run_id: UUID, grace_seconds: float = 30) -> None:
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
