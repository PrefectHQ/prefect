"""Docker Sandboxes backend implemented through the `sbx` CLI."""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pydantic import Field, PrivateAttr

from prefect_sandbox.base import (
    DEFAULT_MAX_OUTPUT_BYTES,
    SandboxBackend,
    SandboxCreationError,
    SandboxError,
    SandboxExecutionError,
    SandboxHandle,
    SandboxHandleError,
    SandboxResult,
    SandboxUnavailableError,
    _shielded,
    _validate_exec_request,
)

__all__ = ["SbxSandbox"]

_UNKNOWN_EXIT_CODE = -1
_BOOKKEEPING_TIMEOUT = 120.0
_BOOKKEEPING_OUTPUT_BYTES = 16 * 1024
_READ_CHUNK_BYTES = 64 * 1024
_WORKSPACE_PREFIX = "prefect-sandbox-"


@dataclass(frozen=True)
class _CommandResult:
    """Bounded result of one host-side CLI invocation."""

    exit_code: int
    stdout: bytes
    stderr: bytes
    truncated: bool


async def _drain_capped(
    stream: asyncio.StreamReader | None, limit: int
) -> tuple[bytes, bool]:
    """Drain a stream to EOF while retaining at most `limit` bytes."""
    if stream is None:
        return b"", False

    retained = bytearray()
    truncated = False
    while chunk := await stream.read(_READ_CHUNK_BYTES):
        remaining = limit - len(retained)
        if remaining > 0:
            retained.extend(chunk[:remaining])
        if len(chunk) > remaining:
            truncated = True
    return bytes(retained), truncated


def _kill_process_tree(process: asyncio.subprocess.Process) -> None:
    """Kill a CLI subprocess and its POSIX process group."""
    if os.name == "posix":
        with suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(process.pid, signal.SIGKILL)
    with suppress(ProcessLookupError):
        process.kill()


def _workspace_path(path: str | Path) -> Path:
    """Resolve an adapter-owned workspace or reject an unsafe path."""
    candidate = Path(path)
    resolved = candidate.resolve(strict=False)
    temp_root = Path(tempfile.gettempdir()).resolve()
    if (
        not candidate.is_absolute()
        or resolved.parent != temp_root
        or not resolved.name.startswith(_WORKSPACE_PREFIX)
    ):
        raise SandboxError(f"refusing to remove unowned workspace {str(path)!r}")
    return resolved


def _remove_workspace(path: Path) -> None:
    """Remove an adapter-owned workspace if it still exists."""
    try:
        shutil.rmtree(_workspace_path(path))
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise SandboxError(f"failed to remove workspace {str(path)!r}: {exc}") from exc


async def _make_workspace_cancellation_safe() -> Path:
    """Finish workspace creation and remove it before delivering cancellation."""
    task = asyncio.create_task(
        asyncio.to_thread(tempfile.mkdtemp, prefix=_WORKSPACE_PREFIX)
    )
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    workspace = _workspace_path(task.result())
    if cancelled:
        await _shielded(asyncio.to_thread(_remove_workspace, workspace))
        raise asyncio.CancelledError
    return workspace


def _remove_staged_file(path: str) -> None:
    """Remove a staged upload, suppressing only an already-absent path."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise SandboxError(f"failed to remove staged file {path!r}: {exc}") from exc


def _stage_file(content: bytes) -> str:
    """Write bytes to a restrictive host temporary file."""
    descriptor, path = tempfile.mkstemp(prefix="prefect-sandbox-upload-")
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(content)
    except BaseException:
        _remove_staged_file(path)
        raise
    return path


async def _stage_file_cancellation_safe(content: bytes) -> str:
    """Finish staging and avoid leaking the file if the caller is cancelled."""
    task = asyncio.create_task(asyncio.to_thread(_stage_file, content))
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    path = task.result()
    if cancelled:
        await _shielded(asyncio.to_thread(_remove_staged_file, path))
        raise asyncio.CancelledError
    return path


def _strip_autostart_notice(stderr: bytes, sandbox_id: str) -> bytes:
    """Remove the provider's sandbox-start notice from command stderr."""
    notice = f"Sandbox {sandbox_id} started successfully".encode()
    return b"".join(
        line for line in stderr.splitlines(keepends=True) if line.strip() != notice
    )


class SbxSandbox(SandboxBackend):
    """Run commands in disposable Docker Sandboxes microVMs.

    The backend gives `sbx` an otherwise empty temporary workspace and retains that
    path only in this backend instance. Host environment variables are available to
    the host-side CLI, but guest commands receive only the values explicitly passed
    to `exec` in addition to image/runtime-provided environment variables.
    """

    _block_type_name = "Docker Sandbox"
    _documentation_url = "https://docs.docker.com/ai/sandboxes/"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/14a315b79990200db7341e42553e23650b34bb96-250x250.png"

    image: str = Field(
        default="python:3.12-slim",
        min_length=1,
        description="Container image used as the sandbox template.",
    )
    memory: str = Field(
        default="2g",
        min_length=1,
        description="Memory limit accepted by `sbx create`, such as `2g`.",
    )
    cpus: int | None = Field(
        default=None,
        gt=0,
        description="CPU count, or the provider default when omitted.",
    )
    sbx_path: str = Field(
        default="sbx",
        min_length=1,
        description="Path to the Docker Sandboxes CLI.",
    )
    create_timeout: float = Field(
        default=600.0,
        gt=0,
        description="Maximum seconds allowed for sandbox creation.",
    )

    _sandboxes: dict[str, Path | None] = PrivateAttr(default_factory=dict)
    _destroy_tasks: dict[str, asyncio.Task[None]] = PrivateAttr(default_factory=dict)

    def _check_binary(self) -> None:
        """Fail clearly when the Docker Sandboxes CLI is unavailable."""
        if shutil.which(self.sbx_path) is None:
            raise SandboxUnavailableError(
                f"{self.sbx_path!r} was not found on PATH; install Docker Sandboxes "
                "and run `sbx login`"
            )

    async def _run_cli(
        self,
        args: Sequence[str],
        *,
        timeout: float | None,
        max_output_bytes: int,
    ) -> _CommandResult:
        """Run one CLI command with bounded output and process-tree cleanup."""
        try:
            process = await asyncio.create_subprocess_exec(
                self.sbx_path,
                *args,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=os.name == "posix",
            )
        except OSError as exc:
            raise SandboxUnavailableError(
                f"could not execute {self.sbx_path!r}: {exc}"
            ) from exc

        readers = (
            asyncio.create_task(_drain_capped(process.stdout, max_output_bytes)),
            asyncio.create_task(_drain_capped(process.stderr, max_output_bytes)),
        )
        completed = asyncio.gather(*readers, process.wait())
        try:
            (
                (stdout, out_truncated),
                (stderr, err_truncated),
                exit_code,
            ) = await asyncio.wait_for(completed, timeout)
        except BaseException:
            completed.cancel()
            _kill_process_tree(process)
            with suppress(BaseException):
                await process.wait()
            await asyncio.gather(*readers, return_exceptions=True)
            raise

        return _CommandResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            truncated=out_truncated or err_truncated,
        )

    def _workspace_for(self, sandbox: SandboxHandle) -> Path:
        """Resolve a live process-local handle to its host workspace."""
        if not isinstance(sandbox, SandboxHandle):
            raise SandboxHandleError("sandbox must be a SandboxHandle")
        if sandbox.id not in self._sandboxes:
            raise SandboxHandleError(
                f"sandbox handle {sandbox.id!r} was not created by this backend"
            )
        workspace = self._sandboxes[sandbox.id]
        if workspace is None:
            raise SandboxHandleError(f"sandbox {sandbox.id!r} was destroyed")
        return workspace

    async def _remove_sandbox(self, sandbox_id: str) -> None:
        """Remove a sandbox or confirm that it is already absent."""
        try:
            removed = await self._run_cli(
                ["rm", "--force", sandbox_id],
                timeout=_BOOKKEEPING_TIMEOUT,
                max_output_bytes=_BOOKKEEPING_OUTPUT_BYTES,
            )
        except asyncio.TimeoutError as exc:
            raise SandboxError(
                f"timed out removing sandbox {sandbox_id!r}; it may still be running"
            ) from exc
        if removed.exit_code == 0:
            return

        try:
            inventory = await self._run_cli(
                ["ls", "--quiet"],
                timeout=_BOOKKEEPING_TIMEOUT,
                max_output_bytes=_BOOKKEEPING_OUTPUT_BYTES,
            )
        except asyncio.TimeoutError as exc:
            raise SandboxError(
                f"could not confirm removal of sandbox {sandbox_id!r}"
            ) from exc

        names = set(inventory.stdout.decode(errors="replace").splitlines())
        if (
            inventory.exit_code == 0
            and not inventory.truncated
            and sandbox_id not in names
        ):
            return
        detail = removed.stderr.decode(errors="replace").strip()[:1000]
        raise SandboxError(
            f"failed to remove sandbox {sandbox_id!r}; it may still be running: "
            f"{detail or '<no output>'}"
        )

    async def _discard(self, sandbox_id: str, workspace: Path) -> None:
        """Attempt provider and host cleanup, reporting every failure."""
        errors: list[Exception | asyncio.CancelledError] = []
        try:
            await self._remove_sandbox(sandbox_id)
        except (SandboxError, asyncio.CancelledError) as exc:
            errors.append(exc)
        try:
            await asyncio.to_thread(_remove_workspace, workspace)
        except (SandboxError, asyncio.CancelledError) as exc:
            errors.append(exc)
        if errors:
            detail = "; ".join(str(error) for error in errors)
            raise SandboxError(detail) from errors[0]

    async def create(self) -> SandboxHandle:
        """Create a usable microVM backed by an empty host workspace."""
        self._check_binary()
        sandbox_id = f"prefect-sandbox-{uuid.uuid4().hex[:12]}"
        workspace = await _make_workspace_cancellation_safe()
        args = [
            "create",
            "--quiet",
            "--name",
            sandbox_id,
            "--memory",
            self.memory,
        ]
        if self.cpus is not None:
            args.extend(["--cpus", str(self.cpus)])
        args.extend(["--template", self.image, "shell", str(workspace)])

        try:
            result = await self._run_cli(
                args,
                timeout=self.create_timeout,
                max_output_bytes=_BOOKKEEPING_OUTPUT_BYTES,
            )
            if result.exit_code != 0:
                detail = result.stderr.decode(errors="replace").strip()[:2000]
                raise SandboxCreationError(
                    f"`sbx create` exited {result.exit_code}: {detail or '<no output>'}"
                )
        except SandboxUnavailableError:
            await _shielded(asyncio.to_thread(_remove_workspace, workspace))
            raise
        except BaseException as create_error:
            try:
                await _shielded(self._discard(sandbox_id, workspace))
            except asyncio.CancelledError:
                raise
            except BaseException as cleanup_error:
                raise SandboxCreationError(
                    f"sandbox creation failed and cleanup could not be confirmed: "
                    f"{create_error}"
                ) from cleanup_error
            if isinstance(create_error, asyncio.TimeoutError):
                raise SandboxCreationError(
                    f"`sbx create` exceeded {self.create_timeout:g} seconds"
                ) from create_error
            raise

        self._sandboxes[sandbox_id] = workspace
        return SandboxHandle(sandbox_id)

    async def exec(
        self,
        sandbox: SandboxHandle,
        command: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    ) -> SandboxResult:
        """Run an argv sequence without invoking a guest shell."""
        _validate_exec_request(command, env, timeout, max_output_bytes)
        self._workspace_for(sandbox)

        args = ["exec"]
        for key, value in (env or {}).items():
            args.extend(["--env", f"{key}={value}"])
        args.append(sandbox.id)
        args.extend(command)

        try:
            result = await self._run_cli(
                args,
                timeout=timeout,
                max_output_bytes=max_output_bytes,
            )
        except asyncio.TimeoutError:
            try:
                await _shielded(self.destroy(sandbox))
            except BaseException as cleanup_error:
                raise SandboxExecutionError(
                    f"command timed out and sandbox {sandbox.id!r} could not be "
                    "confirmed destroyed"
                ) from cleanup_error
            return SandboxResult(
                exit_code=_UNKNOWN_EXIT_CODE,
                stdout=b"",
                stderr=(
                    f"`sbx exec` exceeded {timeout:g} seconds; sandbox destroyed"
                ).encode(),
                timed_out=True,
            )
        except asyncio.CancelledError:
            await _shielded(self.destroy(sandbox))
            raise

        return SandboxResult(
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=_strip_autostart_notice(result.stderr, sandbox.id),
            truncated=result.truncated,
        )

    async def _destroy_once(self, sandbox_id: str, workspace: Path) -> None:
        """Perform the shared cleanup used by concurrent destroy callers."""
        succeeded = False
        try:
            await self._discard(sandbox_id, workspace)
            succeeded = True
        finally:
            if succeeded:
                self._sandboxes[sandbox_id] = None
            if self._destroy_tasks.get(sandbox_id) is asyncio.current_task():
                self._destroy_tasks.pop(sandbox_id, None)

    async def destroy(self, sandbox: SandboxHandle) -> None:
        """Remove one microVM and its temporary host workspace."""
        if not isinstance(sandbox, SandboxHandle):
            raise SandboxHandleError("sandbox must be a SandboxHandle")
        if sandbox.id not in self._sandboxes:
            raise SandboxHandleError(
                f"sandbox handle {sandbox.id!r} was not created by this backend"
            )
        workspace = self._sandboxes[sandbox.id]
        if workspace is None:
            return

        task = self._destroy_tasks.get(sandbox.id)
        if task is None:
            task = asyncio.create_task(self._destroy_once(sandbox.id, workspace))
            self._destroy_tasks[sandbox.id] = task
        await _shielded(task)

    async def write_file(
        self,
        sandbox: SandboxHandle,
        path: str,
        content: bytes,
    ) -> None:
        """Copy bytes into a sandbox using the provider's native file transfer."""
        self._workspace_for(sandbox)
        if not isinstance(path, str) or "\0" in path or not path.startswith("/"):
            raise ValueError("path must be an absolute guest path without null bytes")
        if ".." in PurePosixPath(path).parts:
            raise ValueError("path must not contain parent traversal")
        if not isinstance(content, bytes):
            raise TypeError("content must be bytes")

        parent = str(PurePosixPath(path).parent)
        if parent != "/":
            created = await self.exec(
                sandbox,
                ["mkdir", "-p", parent],
                timeout=_BOOKKEEPING_TIMEOUT,
                max_output_bytes=_BOOKKEEPING_OUTPUT_BYTES,
            )
            if not created.ok:
                raise SandboxExecutionError(
                    f"could not create parent directory {parent!r}: "
                    f"{created.stderr.decode(errors='replace')[:1000]}"
                )

        staged = await _stage_file_cancellation_safe(content)
        try:
            try:
                copied = await self._run_cli(
                    ["cp", staged, f"{sandbox.id}:{path}"],
                    timeout=_BOOKKEEPING_TIMEOUT,
                    max_output_bytes=_BOOKKEEPING_OUTPUT_BYTES,
                )
            except asyncio.TimeoutError as exc:
                raise SandboxExecutionError(
                    f"timed out copying {path!r} into sandbox {sandbox.id!r}"
                ) from exc
            if copied.exit_code != 0:
                detail = copied.stderr.decode(errors="replace").strip()[:1000]
                raise SandboxExecutionError(
                    f"failed to copy {path!r} into sandbox {sandbox.id!r}: "
                    f"{detail or '<no output>'}"
                )
        finally:
            await _shielded(asyncio.to_thread(_remove_staged_file, staged))
