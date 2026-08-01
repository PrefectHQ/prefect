"""Provider-neutral primitives for disposable sandbox execution."""

from __future__ import annotations

import asyncio
import math
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import ClassVar, Protocol, TypeVar, runtime_checkable

from prefect.blocks.core import Block

__all__ = [
    "DEFAULT_MAX_OUTPUT_BYTES",
    "SandboxBackend",
    "SandboxCreationError",
    "SandboxError",
    "SandboxExecutionError",
    "SandboxFileWriter",
    "SandboxHandle",
    "SandboxHandleError",
    "SandboxResult",
    "SandboxUnavailableError",
    "sandbox_session",
]

DEFAULT_MAX_OUTPUT_BYTES = 64 * 1024


class SandboxError(Exception):
    """Base class for sandbox infrastructure failures."""


class SandboxUnavailableError(SandboxError):
    """The selected sandbox provider is not available on this host."""


class SandboxCreationError(SandboxError):
    """A sandbox could not be provisioned or safely cleaned up."""


class SandboxExecutionError(SandboxError):
    """Sandbox infrastructure failed while executing a command."""


class SandboxHandleError(SandboxError):
    """A handle is unknown to the backend or no longer usable."""


@dataclass(frozen=True)
class SandboxHandle:
    """Opaque, process-local reference identifying one sandbox."""

    id: str


@dataclass(frozen=True)
class SandboxResult:
    """Bounded output and status returned by one sandbox command."""

    exit_code: int
    stdout: bytes
    stderr: bytes
    timed_out: bool = False
    truncated: bool = False

    @property
    def ok(self) -> bool:
        """Whether the command completed successfully."""
        return self.exit_code == 0 and not self.timed_out


@runtime_checkable
class SandboxFileWriter(Protocol):
    """Optional capability for providers with native file transfer."""

    async def write_file(
        self,
        sandbox: SandboxHandle,
        path: str,
        content: bytes,
    ) -> None:
        """Write bytes to an absolute path inside `sandbox`."""


def _validate_exec_request(
    command: Sequence[str],
    env: Mapping[str, str] | None,
    timeout: float | None,
    max_output_bytes: int,
) -> None:
    """Reject request values that no provider can safely honor."""
    if isinstance(command, (str, bytes)):
        raise TypeError("command must be an argv sequence, not a string or bytes")
    if not command:
        raise ValueError("command must not be empty")
    for index, value in enumerate(command):
        if not isinstance(value, str):
            raise TypeError(f"command[{index}] must be a string")
        if "\0" in value:
            raise ValueError(f"command[{index}] must not contain a null byte")

    for key, value in (env or {}).items():
        if not isinstance(key, str) or not key or "=" in key or "\0" in key:
            raise ValueError(f"invalid environment variable name: {key!r}")
        if not isinstance(value, str):
            raise TypeError(f"environment variable {key!r} must be a string")
        if "\0" in value:
            raise ValueError(f"environment variable {key!r} contains a null byte")

    if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
        raise ValueError("timeout must be a positive, finite number or None")
    if not isinstance(max_output_bytes, int) or max_output_bytes <= 0:
        raise ValueError("max_output_bytes must be a positive integer")


T = TypeVar("T")


async def _shielded(awaitable: Awaitable[T]) -> T:
    """Finish an awaitable before re-delivering caller cancellation."""
    task = asyncio.ensure_future(awaitable)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    result = task.result()
    if cancelled:
        raise asyncio.CancelledError
    return result


class SandboxBackend(Block, ABC):
    """Minimal lifecycle contract implemented by sandbox providers.

    A handle is trusted only inside the process and backend instance that created it.
    It is not an authenticated or durable token. Implementations must avoid implicit
    host-environment forwarding, retain output only up to `max_output_bytes`, return
    nonzero command exits as data, clean partial creates, and make `destroy`
    idempotent for handles they created. A backend instance and its handles belong to
    one event loop; concurrent tasks on that loop are supported, but sharing them
    across loops, threads, or processes is outside this contract. Process termination
    can orphan provider resources because durable identity and sweeping are deferred.
    """

    _block_schema_capabilities: ClassVar[list[str]] = ["run-in-sandbox"]

    @abstractmethod
    async def create(self) -> SandboxHandle:
        """Provision a usable sandbox and return its opaque handle."""

    @abstractmethod
    async def exec(
        self,
        sandbox: SandboxHandle,
        command: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    ) -> SandboxResult:
        """Execute an argv sequence inside `sandbox`."""

    @abstractmethod
    async def destroy(self, sandbox: SandboxHandle) -> None:
        """Destroy a sandbox, succeeding when it was already destroyed."""


@asynccontextmanager
async def sandbox_session(backend: SandboxBackend) -> AsyncIterator[SandboxHandle]:
    """Create one sandbox and finish its destruction on every exit path."""
    sandbox = await backend.create()
    try:
        yield sandbox
    finally:
        await _shielded(backend.destroy(sandbox))
