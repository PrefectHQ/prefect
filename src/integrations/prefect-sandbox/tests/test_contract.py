import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import FrozenInstanceError

import pytest
from prefect_sandbox import (
    SandboxBackend,
    SandboxFileWriter,
    SandboxHandle,
    SandboxResult,
    sandbox_session,
)
from pydantic import PrivateAttr


class MemoryBackend(SandboxBackend):
    _next_id: int = PrivateAttr(default=0)
    _active: set[str] = PrivateAttr(default_factory=set)
    _destroyed: list[str] = PrivateAttr(default_factory=list)
    _destroy_started: asyncio.Event | None = PrivateAttr(default=None)
    _finish_destroy: asyncio.Event | None = PrivateAttr(default=None)
    _destroy_error: BaseException | None = PrivateAttr(default=None)
    _create_error: BaseException | None = PrivateAttr(default=None)

    async def create(self) -> SandboxHandle:
        if self._create_error is not None:
            raise self._create_error
        self._next_id += 1
        handle = SandboxHandle(f"memory-{self._next_id}")
        self._active.add(handle.id)
        return handle

    async def exec(
        self,
        sandbox: SandboxHandle,
        command: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
        max_output_bytes: int = 64 * 1024,
    ) -> SandboxResult:
        assert sandbox.id in self._active
        return SandboxResult(0, b"\0".join(value.encode() for value in command), b"")

    async def destroy(self, sandbox: SandboxHandle) -> None:
        if sandbox.id not in self._active:
            return
        if self._destroy_started is not None:
            self._destroy_started.set()
        if self._finish_destroy is not None:
            await self._finish_destroy.wait()
        if self._destroy_error is not None:
            raise self._destroy_error
        self._active.remove(sandbox.id)
        self._destroyed.append(sandbox.id)


class MemoryFileWriter:
    async def write_file(
        self, sandbox: SandboxHandle, path: str, content: bytes
    ) -> None:
        pass


def test_value_types_are_frozen() -> None:
    handle = SandboxHandle("sandbox")
    result = SandboxResult(0, b"out", b"err")

    with pytest.raises(FrozenInstanceError):
        handle.id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.exit_code = 1  # type: ignore[misc]


def test_result_ok_requires_success_without_timeout() -> None:
    assert SandboxResult(0, b"", b"").ok
    assert not SandboxResult(1, b"", b"").ok
    assert not SandboxResult(-1, b"", b"", timed_out=True).ok


def test_file_writer_is_a_structural_optional_capability() -> None:
    assert isinstance(MemoryFileWriter(), SandboxFileWriter)
    assert not isinstance(MemoryBackend(), SandboxFileWriter)


async def test_backend_can_serve_distinct_concurrent_handles() -> None:
    backend = MemoryBackend()

    first, second = await asyncio.gather(backend.create(), backend.create())
    results = await asyncio.gather(
        backend.exec(first, ["one", "argument with spaces"]),
        backend.exec(second, ["two"]),
    )

    assert first != second
    assert results[0].stdout == b"one\0argument with spaces"
    assert results[1].stdout == b"two"


async def test_session_destroys_after_success() -> None:
    backend = MemoryBackend()

    async with sandbox_session(backend) as sandbox:
        assert sandbox.id in backend._active

    assert sandbox.id not in backend._active
    assert backend._destroyed == [sandbox.id]


async def test_session_destroys_after_body_failure() -> None:
    backend = MemoryBackend()

    with pytest.raises(ValueError, match="body failed"):
        async with sandbox_session(backend) as sandbox:
            raise ValueError("body failed")

    assert sandbox.id not in backend._active


async def test_session_finishes_cleanup_before_redelivering_cancellation() -> None:
    backend = MemoryBackend()
    backend._destroy_started = asyncio.Event()
    backend._finish_destroy = asyncio.Event()
    body_started = asyncio.Event()

    async def run_session() -> None:
        async with sandbox_session(backend):
            body_started.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(run_session())
    await body_started.wait()
    task.cancel()
    await backend._destroy_started.wait()

    assert not task.done()
    backend._finish_destroy.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not backend._active


async def test_session_surfaces_cleanup_failure() -> None:
    backend = MemoryBackend()
    backend._destroy_error = RuntimeError("cleanup failed")

    with pytest.raises(RuntimeError, match="cleanup failed"):
        async with sandbox_session(backend):
            pass


async def test_failed_create_does_not_call_destroy() -> None:
    backend = MemoryBackend()
    backend._create_error = RuntimeError("create failed")

    with pytest.raises(RuntimeError, match="create failed"):
        async with sandbox_session(backend):
            pass

    assert backend._destroyed == []
