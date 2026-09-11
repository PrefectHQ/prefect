from __future__ import annotations

import asyncio
import ctypes
import multiprocessing.context
import os
import signal
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

import anyio
import anyio.abc
from typing_extensions import Self

from prefect.logging import get_logger

_WINDOWS_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_WINDOWS_PROCESS_SET_QUOTA = 0x0100
_WINDOWS_PROCESS_TERMINATE = 0x0001
_WINDOWS_SYNCHRONIZE = 0x00100000
_WINDOWS_PROCESS_PROBE_ACCESS = (
    _WINDOWS_PROCESS_QUERY_LIMITED_INFORMATION | _WINDOWS_SYNCHRONIZE
)
_WINDOWS_WAIT_OBJECT_0 = 0x00000000
_WINDOWS_WAIT_TIMEOUT = 0x00000102
_WINDOWS_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_WINDOWS_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_windows_kernel32: ctypes.WinDLL | None = None


class _WindowsJobObjectBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _WindowsIoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _WindowsJobObjectExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _WindowsJobObjectBasicLimitInformation),
        ("IoInfo", _WindowsIoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _get_windows_kernel32() -> ctypes.WinDLL:
    global _windows_kernel32

    if _windows_kernel32 is None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.WaitForSingleObject.restype = ctypes.c_uint32
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        kernel32.SetInformationJobObject.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        kernel32.SetInformationJobObject.restype = ctypes.c_int
        kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel32.AssignProcessToJobObject.restype = ctypes.c_int
        kernel32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.TerminateJobObject.restype = ctypes.c_int
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
        return wait_result != _WINDOWS_WAIT_OBJECT_0
    finally:
        kernel32.CloseHandle(handle)


class ProcessTerminationScope(Protocol):
    wait_after_graceful_kill: bool

    def is_alive(self, pid: int) -> bool: ...

    def graceful_kill(self, pid: int) -> None: ...

    def hard_kill(self, pid: int) -> None: ...

    def close(self) -> None: ...


class _SingleProcessTerminationScope:
    wait_after_graceful_kill = sys.platform != "win32"

    def is_alive(self, pid: int) -> bool:
        return _pid_is_alive(pid)

    def graceful_kill(self, pid: int) -> None:
        if sys.platform == "win32":
            os.kill(pid, signal.CTRL_BREAK_EVENT)
        else:
            os.kill(pid, signal.SIGTERM)

    def hard_kill(self, pid: int) -> None:
        if sys.platform == "win32":
            # Any signal other than the CTRL_* events is a TerminateProcess here.
            os.kill(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGKILL)

    def close(self) -> None:
        pass


class _PosixProcessGroupTerminationScope:
    wait_after_graceful_kill = True

    def is_alive(self, pid: int) -> bool:
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        else:
            return True

    def graceful_kill(self, pid: int) -> None:
        os.killpg(pid, signal.SIGTERM)

    def hard_kill(self, pid: int) -> None:
        os.killpg(pid, signal.SIGKILL)

    def close(self) -> None:
        pass


class _WindowsJobTerminationScope:
    wait_after_graceful_kill = False

    def __init__(self, job_handle: int) -> None:
        self._job_handle = job_handle

    def is_alive(self, pid: int) -> bool:
        return _pid_is_alive(pid)

    def graceful_kill(self, pid: int) -> None:
        os.kill(pid, signal.CTRL_BREAK_EVENT)

    def hard_kill(self, pid: int) -> None:
        if not _get_windows_kernel32().TerminateJobObject(self._job_handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self._job_handle:
            _get_windows_kernel32().CloseHandle(self._job_handle)
            self._job_handle = 0


def _create_windows_job_termination_scope(pid: int) -> _WindowsJobTerminationScope:
    kernel32 = _get_windows_kernel32()
    job_handle = kernel32.CreateJobObjectW(None, None)
    if not job_handle:
        raise ctypes.WinError(ctypes.get_last_error())

    try:
        limits = _WindowsJobObjectExtendedLimitInformation()
        limits.BasicLimitInformation.LimitFlags = (
            _WINDOWS_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        if not kernel32.SetInformationJobObject(
            job_handle,
            _WINDOWS_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        process_handle = kernel32.OpenProcess(
            _WINDOWS_PROCESS_SET_QUOTA
            | _WINDOWS_PROCESS_TERMINATE
            | _WINDOWS_PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            pid,
        )
        if not process_handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not kernel32.AssignProcessToJobObject(job_handle, process_handle):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel32.CloseHandle(process_handle)
    except BaseException:
        kernel32.CloseHandle(job_handle)
        raise

    return _WindowsJobTerminationScope(job_handle)


def create_isolated_termination_scope(pid: int) -> ProcessTerminationScope:
    if sys.platform == "win32":
        return _create_windows_job_termination_scope(pid)
    return _PosixProcessGroupTerminationScope()


@dataclass
class ProcessHandle:
    """A tracked child and the platform-specific scope its starter owns."""

    _process: anyio.abc.Process | multiprocessing.context.SpawnProcess
    termination_scope: ProcessTerminationScope = field(
        default_factory=_SingleProcessTerminationScope
    )

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

    def is_alive(self) -> bool:
        return self.pid is not None and self.termination_scope.is_alive(self.pid)

    def graceful_kill(self) -> None:
        if self.pid is not None:
            self.termination_scope.graceful_kill(self.pid)

    def hard_kill(self) -> None:
        if self.pid is not None:
            self.termination_scope.hard_kill(self.pid)

    def close(self) -> None:
        self.termination_scope.close()


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

    async def __aenter__(self) -> Self:
        self._lock = asyncio.Lock()
        return self

    async def __aexit__(self, *_: object) -> None:
        async with self._process_map_lock:
            flow_run_ids = list(self._process_map.keys())

        for flow_run_id in flow_run_ids:
            try:
                await self.kill(flow_run_id)
            except Exception:
                self._logger.exception(
                    "Failed to kill process for flow run '%s' during shutdown.",
                    flow_run_id,
                )

        async with self._process_map_lock:
            handles = list(self._process_map.values())
            self._process_map.clear()
        for handle in handles:
            handle.close()

    async def add(self, flow_run_id: UUID, handle: ProcessHandle) -> None:
        async with self._process_map_lock:
            self._process_map[flow_run_id] = handle

        if self._on_add is not None:
            try:
                await self._on_add(flow_run_id)
            except Exception:
                self._logger.exception(
                    "on_add callback raised for flow run '%s'",
                    flow_run_id,
                )

    async def remove(self, flow_run_id: UUID) -> None:
        async with self._process_map_lock:
            handle = self._process_map.pop(flow_run_id, None)

        if handle is not None:
            handle.close()

        if self._on_remove is not None:
            try:
                await self._on_remove(flow_run_id)
            except Exception:
                self._logger.exception(
                    "on_remove callback raised for flow run '%s'",
                    flow_run_id,
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

            pid = handle.pid
            if pid is None:
                return True

            if not handle.is_alive():
                return True

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False

            await anyio.sleep(min(check_interval, remaining))

    async def kill(
        self, flow_run_id: UUID, grace_seconds: float = 30, *, force: bool = False
    ) -> None:
        """Stop the process for `flow_run_id`.

        `force` skips the graceful signal, for callers that must not let the process
        run any more code; `grace_seconds` is unused in that case.
        """
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

        if force:
            try:
                handle.hard_kill()
            except ProcessLookupError:
                pass
            return

        try:
            handle.graceful_kill()
        except ProcessLookupError:
            # Already reaped, e.g. re-killed from `__aexit__` after a cancelled
            # executor skipped its cleanup.
            return

        if handle.termination_scope.wait_after_graceful_kill:
            check_interval = max(grace_seconds / 10, 1)
            with anyio.move_on_after(grace_seconds):
                while True:
                    await anyio.sleep(check_interval)
                    if not handle.is_alive():
                        return
            try:
                handle.hard_kill()
            except OSError:
                return
