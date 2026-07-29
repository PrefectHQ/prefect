"""Run a list of commands inside a disposable, kernel-isolated sandbox.

`SandboxOperation` is the sandbox counterpart to `prefect_shell.ShellOperation`: the
same `trigger`/`wait`/`fetch` and `run` ergonomics, the same `a`-prefixed async twins,
the same context-manager cleanup. The difference is where the commands land — an
ephemeral microVM that is destroyed afterwards and that inherits none of the worker's
credentials, instead of a subprocess on the worker itself.
"""

from __future__ import annotations

import asyncio
import math
import os
from collections.abc import Mapping, Sequence
from threading import Lock
from typing import Any

from typing_extensions import Self

from prefect._internal.compatibility.async_dispatch import async_dispatch
from prefect.blocks.abstract import JobRun, LoggerOrAdapter
from prefect.exceptions import MissingContextError
from prefect.logging import get_logger, get_run_logger
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect_sandbox.base import (
    Sandbox,
    SandboxBackend,
    SandboxError,
    SandboxResult,
    _shielded_cleanup,
    validate_env,
)

__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "SandboxOperation",
    "SandboxProcess",
]

#: Default wall-clock budget for one `SandboxOperation`. `SandboxBackend.aexec`
#: requires a concrete timeout — there is no "run forever" — and an unbounded default
#: is the wrong posture for code the caller did not author.
DEFAULT_TIMEOUT_SECONDS = 600.0


def _consume_task_result(task: asyncio.Future[Any]) -> None:
    """Retrieve a finished task's exception to prevent asyncio warnings."""
    if not task.cancelled():
        task.exception()


def _cancel_and_consume_task(task: asyncio.Task[Any]) -> None:
    """Cancel a task on its owning loop and retrieve its eventual exception."""
    task.cancel()
    task.add_done_callback(_consume_task_result)


class SandboxProcess(JobRun[list[str]]):
    """One execution of a command sequence inside one sandbox, which it owns.

    Where `prefect_shell.ShellProcess` borrows a live process object from the block
    that spawned it and leaves teardown on that block's shared exit stacks, a
    `SandboxProcess` owns its sandbox outright: the handle, the in-flight execution and
    the teardown all live here. That is what makes concurrent
    `SandboxOperation.atrigger()` calls independent — closing one process destroys only
    its own sandbox.

    Attributes:
        sandbox: Handle to the sandbox the commands are running in.
        result: The full `SandboxResult` once the commands have finished, otherwise
            `None`. A sandbox result carries strictly more than a shell one — exit
            code, stderr, `timed_out`, `truncated`, `sandbox_terminated` — and
            `fetch_result` can only return stdout lines, so this is where the rest is.
    """

    def __init__(
        self,
        *,
        backend: SandboxBackend,
        sandbox: Sandbox,
        command: Sequence[str],
        timeout: float,
        env: Mapping[str, str] | None = None,
        working_dir: str | None = None,
        stream_output: bool = True,
        raise_on_failure: bool = True,
    ) -> None:
        """Wrap a provisioned sandbox and the command that is about to run in it.

        Args:
            backend: Backend that provisioned `sandbox` and will tear it down.
            sandbox: Handle returned by `SandboxBackend.acreate`.
            command: Argv to execute, already assembled by the caller.
            timeout: Seconds the command may run before the backend stops it.
            env: Environment variables to set for this command only.
            working_dir: Directory inside the sandbox to run in.
            stream_output: Whether to relay captured output to the run logger.
            raise_on_failure: Whether `await_for_completion` raises on a nonzero exit.
        """
        self.sandbox = sandbox
        self.result: SandboxResult | None = None
        self._backend = backend
        self._command = list(command)
        self._timeout = timeout
        self._env = dict(env or {})
        self._working_dir = working_dir
        self._stream_output = stream_output
        self._raise_on_failure = raise_on_failure
        self._output: list[str] = []
        self._task: asyncio.Task[SandboxResult] | None = None
        self._closed = False

    @property
    def return_code(self) -> int | None:
        """The command's exit status, or `None` while it is still running.

        Returns:
            The exit code, or `None` if the commands have not finished. Meaningless
            when `result.timed_out` is set — consult `result` for that.
        """
        return None if self.result is None else self.result.exit_code

    def _start(self) -> None:
        """Put the execution in flight on the running event loop.

        `SandboxBackend` exposes a single awaitable `aexec` and no polling handle, so
        "triggered" means a task is running; `await_for_completion` joins it. Called
        once by `SandboxOperation` right after the sandbox is provisioned.
        """
        if self._task is None:
            self._task = asyncio.ensure_future(self._aexecute())

    async def _aexecute(self) -> SandboxResult:
        """Run the command in the sandbox and record its outcome."""
        result = await self._backend.aexec(
            self.sandbox,
            self._command,
            timeout=self._timeout,
            # An empty mapping and `None` mean the same thing to a backend; pass
            # `None` so backends can skip building an `env` wrapper entirely.
            env=self._env or None,
            working_dir=self._working_dir,
        )
        self.result = result
        self._output = result.stdout.splitlines()
        if self._stream_output:
            self._log_output(result)
        return result

    def _log_output(self, result: SandboxResult) -> None:
        """Relay the sandbox's captured output to the run logger, one record per line.

        `aexec` caps output as it streams but hands back only a finished
        `SandboxResult`, so — unlike `ShellOperation`, which logs each chunk as the
        pipe yields it — these records are emitted once the command has exited.
        """
        for line in result.stdout.splitlines():
            self.logger.info(f"{self.sandbox} stream output:{os.linesep}{line}")
        for line in result.stderr.splitlines():
            self.logger.info(f"{self.sandbox} stderr:{os.linesep}{line}")
        if result.truncated:
            self.logger.warning(
                f"{self.sandbox} output was truncated at the backend's "
                f"{self._backend.max_output_bytes}-byte cap."
            )

    async def await_for_completion(self) -> None:
        """Wait for the commands to finish (async version).

        Raises:
            RuntimeError: If this process was never started.
            SandboxExecutionError: If the commands failed or timed out and
                `raise_on_failure` is set.
        """
        if self._task is None:
            raise RuntimeError(
                "This SandboxProcess was never started. Obtain one from "
                "SandboxOperation.atrigger() rather than constructing it directly."
            )
        self.logger.debug(f"Waiting for {self.sandbox} to complete.")
        result = await self._task

        if result.timed_out:
            self.logger.warning(
                f"{self.sandbox} timed out after {self._timeout} seconds."
                + (
                    " The sandbox was destroyed to stop it."
                    if result.sandbox_terminated
                    else ""
                )
            )
        if self._raise_on_failure:
            result.raise_for_status()
        self.logger.info(f"{self.sandbox} completed with exit code {result.exit_code}.")

    @async_dispatch(await_for_completion)
    def wait_for_completion(self) -> None:
        """Wait for the commands to finish (sync version)."""
        run_coro_as_sync(self.await_for_completion())

    def _result_lines(self) -> list[str]:
        """Snapshot the captured stdout lines, noting if the run is unfinished."""
        if self.result is None:
            self.logger.info("Commands are still running, result may be incomplete.")
        # A copy, not the live list: `ShellProcess.fetch_result` hands back its own
        # mutable buffer, which lets a caller corrupt the run's own record of output.
        return list(self._output)

    async def afetch_result(self) -> list[str]:
        """Retrieve the sandbox's captured stdout (async version).

        Returns:
            The stdout lines. stderr is deliberately excluded and is available in full
            on `result.stderr`: `SandboxResult` keeps the two streams apart, and
            merging them here would throw that distinction away. (`ShellProcess` folds
            stderr into the result on its async path but not its sync one; there is no
            consistent behaviour there to preserve.)
        """
        return self._result_lines()

    @async_dispatch(afetch_result)
    def fetch_result(self) -> list[str]:
        """Retrieve the sandbox's captured stdout (sync version).

        Returns:
            The stdout lines, exactly as `afetch_result` returns them.
        """
        return self._result_lines()

    async def aclose(self) -> None:
        """Destroy this process's sandbox, cancelling the commands if still running.

        Idempotent, and safe to call while another `SandboxProcess` from the same
        `SandboxOperation` is mid-flight.
        """
        if self._closed:
            return
        self._closed = True
        try:
            if self._task is not None:
                task_loop = self._task.get_loop()
                current_loop = asyncio.get_running_loop()
                if task_loop is current_loop:
                    if not self._task.done():
                        self._task.cancel()
                    # Consume the outcome so a failed or cancelled execution cannot
                    # resurface later as an "exception was never retrieved" warning.
                    await asyncio.gather(self._task, return_exceptions=True)
                elif self._task.done():
                    _consume_task_result(self._task)
                else:
                    # A sync context manager used inside async code closes on
                    # Prefect's sync loop thread. It cannot await a task owned by the
                    # blocked caller loop, so queue cancellation and exception
                    # retrieval there; destroying the sandbox below stops the actual
                    # external command before this method returns.
                    task_loop.call_soon_threadsafe(_cancel_and_consume_task, self._task)
        finally:
            try:
                await _shielded_cleanup(self._backend.adestroy(self.sandbox))
            except BaseException:
                # A failed destroy must remain retryable; `adestroy` is idempotent.
                self._closed = False
                raise
            self.logger.info(f"Destroyed {self.sandbox}.")

    @async_dispatch(aclose)
    def close(self) -> None:
        """Destroy this process's sandbox (sync version)."""
        run_coro_as_sync(self.aclose())

    async def __aenter__(self) -> Self:
        """Enter the process context; the sandbox is already provisioned."""
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Destroy the sandbox on leaving the async context."""
        try:
            await self.aclose()
        except Exception:
            if exc_info and exc_info[0] is not None:
                self.logger.exception(
                    f"Failed to destroy {self.sandbox} while handling another error; "
                    "it may still be running."
                )
                return
            raise

    def __enter__(self) -> Self:
        """Enter the process context; the sandbox is already provisioned."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Destroy the sandbox on leaving the sync context."""
        # `_sync=True` rather than a bare `self.close()`: inside an async context the
        # dispatcher would hand back an un-awaited coroutine and the sandbox would
        # leak. `ShellOperation.__exit__` has exactly that bug.
        try:
            self.close(_sync=True)
        except Exception:
            if exc_info and exc_info[0] is not None:
                self.logger.exception(
                    f"Failed to destroy {self.sandbox} while handling another error; "
                    "it may still be running."
                )
                return
            raise


class SandboxOperation:
    """A list of commands to run inside a disposable, kernel-isolated sandbox.

    Read this as "`ShellOperation`, but the commands run inside a sandbox": `trigger()`
    for long-running work you want to supervise, `run()` for short work, `a`-prefixed
    twins for async callers, and context-manager support that tears down everything the
    operation created.

    This is deliberately **not** a Prefect Block, and it must stay that way. `backend`
    is typed as the abstract `SandboxBackend`, and `Block.save()` recursively registers
    the block types found in a block's field annotations; `register_type_and_schema`
    refuses any Block whose direct bases include `ABC`
    (`prefect/blocks/core.py:1492`), which `SandboxBackend(Block, ABC)` does. A Block
    with a `SandboxBackend` field therefore raises `InvalidBlockRegistration` the
    moment anybody saves it — verified empirically, not inferred. The *backends* are
    Blocks, which is where persisted, UI-editable configuration and `SecretStr`
    credentials belong. Commands belong in code.

    Args:
        backend: The sandbox provider to run in, e.g. `SbxSandbox`.
        commands: Commands to execute sequentially in a single shell inside the
            sandbox. The operation's exit status is the last command's.
        env: Environment variables to set for the commands. Nothing is inherited from
            the worker: whatever is not listed here does not exist in the sandbox.
        working_dir: Directory *inside the sandbox* to run in. Unlike
            `ShellOperation.working_dir` this is a plain string, not a validated
            `DirectoryPath` — the path has to exist in the guest, and validating it
            against the worker's filesystem would reject every correct value.
        shell: Shell to interpret `commands` with. Defaults to `sh`, not `bash`,
            because slim sandbox images frequently ship no bash.
        timeout: Seconds the commands may run before the backend stops them.
        files: Files to write into the sandbox before the commands run, as
            `{path: content}`, via `SandboxBackend.awrite_file`. This is how
            model-generated source gets in without riding on a command line.
        stream_output: Whether to relay the sandbox's captured output to the run
            logger.
        raise_on_failure: Whether a nonzero exit raises `SandboxExecutionError`. Set
            `False` to treat the exit code as data and read it off
            `SandboxProcess.result`.

    Examples:
        Run two commands in a fresh sandbox and get their output:
        ```python
        from prefect_sandbox import SandboxOperation, SbxSandbox

        output = await SandboxOperation(
            SbxSandbox(image="python:3.12-slim"),
            ["pip install --quiet requests", "python -c 'import requests; print(requests.__version__)'"],
        ).arun()
        ```

        Supervise a long-running command and keep the full result:
        ```python
        from prefect_sandbox import SandboxOperation, SbxSandbox

        operation = SandboxOperation(SbxSandbox(), ["./train.sh"], timeout=3600)
        async with operation:
            process = await operation.atrigger()
            await process.await_for_completion()
            lines = await process.afetch_result()
            print(process.result.exit_code, process.result.truncated)
        ```
    """

    def __init__(
        self,
        backend: SandboxBackend,
        commands: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        working_dir: str | None = None,
        shell: str = "sh",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        files: Mapping[str, str] | None = None,
        stream_output: bool = True,
        raise_on_failure: bool = True,
    ) -> None:
        """Validate and record the operation's configuration.

        Raises:
            ValueError: If `commands` is empty, `timeout` is not positive, or `env`
                holds a name a POSIX `env` invocation cannot express.
        """
        if not commands:
            raise ValueError("`commands` must contain at least one command.")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError(
                f"`timeout` must be a positive, finite number, got {timeout!r}."
            )
        # Fail here rather than deep inside a backend's argv assembly, where the error
        # would name a shell fragment instead of the offending variable.
        validate_env(env)

        self.backend = backend
        self.commands = list(commands)
        self.env = dict(env or {})
        self.working_dir = working_dir
        self.shell = shell
        self.timeout = timeout
        self.files = dict(files or {})
        self.stream_output = stream_output
        self.raise_on_failure = raise_on_failure

        # Per-process bookkeeping, NOT a shared exit stack. `ShellOperation` pushes
        # every triggered process onto one instance-level `AsyncExitStack` that
        # `close()` unwinds wholesale, so two concurrent triggers on one instance
        # cannot be closed independently. Here each `SandboxProcess` owns its own
        # teardown and this list only records which ones are still outstanding.
        self._processes: list[SandboxProcess] = []
        self._provisioning: set[asyncio.Task[object]] = set()
        # Sandboxes that exist but are not yet attached to a `SandboxProcess`, keyed by
        # the task provisioning them. A closer running on a different event loop cannot
        # join that task — the thread owning its loop is blocked inside `close()` — so
        # this handle is the only thing that lets such a closer destroy the sandbox
        # instead of abandoning it.
        self._provisioned: dict[asyncio.Task[object], Sandbox] = {}
        self._close_generation = 0
        self._active_closers = 0
        # Guards the list against the sync lane (which runs on a separate
        # `run_coro_as_sync` loop thread) mutating it concurrently with the async one.
        self._lock = Lock()

    @property
    def logger(self) -> LoggerOrAdapter:
        """A run logger when inside a flow or task run, else a logger named for the class.

        Copied from `prefect.blocks.abstract`, which defines this property on every
        abstract block base rather than on `Block` itself. `SandboxOperation` is not a
        Block at all, so it has to define it too, and it must degrade gracefully:
        operations are frequently driven from plain scripts.

        Returns:
            The run logger, or a default logger labelled with the class's name.
        """
        try:
            return get_run_logger()
        except MissingContextError:
            return get_logger(self.__class__.__name__)

    def _build_command(self) -> list[str]:
        r"""Assemble the argv that runs every command, in order, in one shell.

        Joined with `"\n"` and not `os.linesep`: the sandbox guest is Linux whatever
        the worker runs on, and a `\r\n`-joined script makes `sh` choke on trailing
        carriage returns.
        """
        return [self.shell, "-c", "\n".join(self.commands)]

    async def _aprovision(self) -> SandboxProcess:
        """Create a sandbox, seed `files` into it, and start the commands.

        Any failure after `acreate` destroys the sandbox before propagating, so a
        half-provisioned operation never leaves a microVM running.
        """
        sandbox = await self.backend.acreate()
        # Publish the handle the moment it exists, before any of the work below that
        # can take a while — seeding files, in particular. Until the `SandboxProcess`
        # is appended to `_processes`, this is the only record a concurrent closer has.
        provisioner = asyncio.current_task()
        if provisioner is not None:
            with self._lock:
                self._provisioned[provisioner] = sandbox
        try:
            for path, content in self.files.items():
                await self.backend.awrite_file(sandbox, path, content)
            process = SandboxProcess(
                backend=self.backend,
                sandbox=sandbox,
                command=self._build_command(),
                timeout=self.timeout,
                env=self.env,
                working_dir=self.working_dir,
                stream_output=self.stream_output,
                raise_on_failure=self.raise_on_failure,
            )
            process._start()
        except BaseException:
            await _shielded_cleanup(self.backend.adestroy(sandbox))
            raise

        self.logger.info(
            f"{sandbox} triggered with {len(self.commands)} commands running "
            f"inside the {(self.working_dir or '.')!r} directory."
        )
        return process

    async def _aprovision_tracked(self) -> SandboxProcess:
        """Provision while coordinating with concurrent operation closure."""
        task = asyncio.current_task()
        if task is None:  # pragma: no cover - every coroutine runs in a task here
            raise RuntimeError("Sandbox provisioning requires an asyncio task.")
        with self._lock:
            if self._active_closers:
                raise SandboxError(
                    "Cannot provision a sandbox while the operation closes."
                )
            generation = self._close_generation
            self._provisioning.add(task)
        try:
            process = await self._aprovision()
            with self._lock:
                close_raced = (
                    generation != self._close_generation or self._active_closers > 0
                )
                if not close_raced:
                    self._processes.append(process)
            if close_raced:
                await process.aclose()
                raise SandboxError(
                    "Sandbox provisioning raced operation closure; the new sandbox "
                    "was destroyed."
                )
            return process
        finally:
            with self._lock:
                self._provisioning.discard(task)
                self._provisioned.pop(task, None)

    async def atrigger(self) -> SandboxProcess:
        """Provision a sandbox, start the commands in it, and return a handle (async version).

        Ideal for long-running commands; for short ones use `arun`, which cleans up on
        your behalf. Every call gets its own sandbox, so concurrent calls on a single
        operation are independent — `SandboxProcess.aclose()` destroys only that call's
        sandbox, and `aclose()` on the operation reclaims whichever ones are left.

        Returns:
            A `SandboxProcess` tracking the newly provisioned sandbox.

        Examples:
            Sleep for 5 seconds and then print "Hello, world!":
            ```python
            from prefect_sandbox import SandboxOperation, SbxSandbox

            async with SandboxOperation(
                SbxSandbox(), ["sleep 5", "echo 'Hello, world!'"]
            ) as operation:
                process = await operation.atrigger()
                await process.await_for_completion()
                output = await process.afetch_result()
            ```
        """
        return await self._aprovision_tracked()

    @async_dispatch(atrigger)
    def trigger(self) -> SandboxProcess:
        """Provision a sandbox and start the commands in it (sync version).

        Returns:
            A `SandboxProcess` tracking the newly provisioned sandbox.

        Examples:
            Sleep for 5 seconds and then print "Hello, world!":
            ```python
            from prefect_sandbox import SandboxOperation, SbxSandbox

            with SandboxOperation(
                SbxSandbox(), ["sleep 5", "echo 'Hello, world!'"]
            ) as operation:
                process = operation.trigger()
                process.wait_for_completion()
                output = process.fetch_result()
            ```
        """
        return run_coro_as_sync(self.atrigger())

    async def arun(self) -> list[str]:
        """Provision, run, fetch, and destroy, in one call (async version).

        Ideal for short-lived commands. The sandbox is destroyed before this returns,
        including on failure. It is tracked only while active so a concurrent
        `aclose()` can cancel it, then removed after its own cleanup.

        Returns:
            The stdout lines produced by the commands.

        Raises:
            SandboxExecutionError: If the commands failed or timed out and
                `raise_on_failure` is set.

        Examples:
            Sleep for 5 seconds and then print "Hello, world!":
            ```python
            from prefect_sandbox import SandboxOperation, SbxSandbox

            output = await SandboxOperation(
                SbxSandbox(), ["sleep 5", "echo 'Hello, world!'"]
            ).arun()
            ```
        """
        process = await self._aprovision_tracked()
        try:
            await process.await_for_completion()
            return await process.afetch_result()
        finally:
            try:
                await process.aclose()
            finally:
                with self._lock:
                    if process in self._processes:
                        self._processes.remove(process)

    @async_dispatch(arun)
    def run(self) -> list[str]:
        """Provision, run, fetch, and destroy, in one call (sync version).

        Returns:
            The stdout lines produced by the commands.

        Examples:
            Sleep for 5 seconds and then print "Hello, world!":
            ```python
            from prefect_sandbox import SandboxOperation, SbxSandbox

            output = SandboxOperation(
                SbxSandbox(), ["sleep 5", "echo 'Hello, world!'"]
            ).run()
            ```
        """
        return run_coro_as_sync(self.arun())

    async def aclose(self) -> None:
        """Destroy every sandbox this operation created and still tracks (async version).

        Outstanding `atrigger()` results and an active `arun()` are tracked. A process
        already closed through its own `aclose()` is skipped. Every teardown is
        attempted. Failures are logged and then raised after the remaining sandboxes
        have been handled. The context-manager exits suppress that cleanup error only
        when a different exception is already leaving the body.

        Provisioning still in flight on *this* event loop is cancelled before this
        returns. Provisioning on another loop cannot be — a `with` block inside async
        code closes on Prefect's sync loop while the thread owning the provisioning loop
        is blocked here, so joining that task would deadlock. Its cancellation is
        scheduled instead, and any sandbox it had already created is destroyed by this
        call, so nothing is left running either way.
        """
        current_loop = asyncio.get_running_loop()
        with self._lock:
            self._active_closers += 1
            self._close_generation += 1
            processes, self._processes = self._processes, []
            provisioning = list(self._provisioning)
            # Sandboxes belonging to provisioning this closer cannot join. Destroying
            # them here is what keeps a scheduled-but-not-awaited cancellation from
            # abandoning a live microVM.
            orphans = [
                sandbox
                for task, sandbox in self._provisioned.items()
                if task.get_loop() is not current_loop
            ]
        try:
            local_provisioning: list[asyncio.Task[object]] = []
            for task in provisioning:
                if task.get_loop() is current_loop:
                    task.cancel()
                    local_provisioning.append(task)
                else:
                    task_loop = task.get_loop()
                    task_loop.call_soon_threadsafe(_cancel_and_consume_task, task)
            if local_provisioning:
                await asyncio.gather(*local_provisioning, return_exceptions=True)

            failures: list[Exception] = []
            failed_processes: list[SandboxProcess] = []
            for sandbox in orphans:
                # `adestroy` is idempotent, so racing the cancelled provisioner's own
                # cleanup is harmless; both outcomes end with the sandbox gone.
                try:
                    await _shielded_cleanup(self.backend.adestroy(sandbox))
                except Exception as exc:
                    failures.append(exc)
                    self.logger.exception(
                        f"Failed to destroy {sandbox}; it may still be running."
                    )
            for process in processes:
                try:
                    await process.aclose()
                except Exception as exc:
                    failures.append(exc)
                    failed_processes.append(process)
                    self.logger.exception(
                        f"Failed to destroy {process.sandbox}; it may still be running."
                    )
            if failures:
                with self._lock:
                    self._processes.extend(failed_processes)
                raise SandboxError(
                    f"Failed to destroy {len(failures)} of "
                    f"{len(processes) + len(orphans)} sandboxes; see the preceding "
                    "errors for sandbox identifiers."
                ) from failures[0]
            # Counting the orphans separately matters: reporting only the processes
            # would log a confident "closed 0 open sandboxes" in exactly the case where
            # a sandbox existed and had to be cleaned up out of band.
            if orphans:
                self.logger.info(
                    f"Successfully closed {len(processes)} open sandboxes and "
                    f"{len(orphans)} still being provisioned on another event loop."
                )
            else:
                self.logger.info(
                    f"Successfully closed {len(processes)} open sandboxes."
                )
        finally:
            with self._lock:
                self._active_closers -= 1

    @async_dispatch(aclose)
    def close(self) -> None:
        """Destroy every sandbox this operation created and still tracks (sync version)."""
        run_coro_as_sync(self.aclose())

    async def __aenter__(self) -> Self:
        """Enter the operation context; no sandbox is provisioned until you trigger."""
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Destroy every outstanding sandbox on leaving the async context."""
        try:
            await self.aclose()
        except Exception:
            if exc_info and exc_info[0] is not None:
                self.logger.exception(
                    "Sandbox cleanup failed while handling another error."
                )
                return
            raise

    def __enter__(self) -> Self:
        """Enter the operation context; no sandbox is provisioned until you trigger."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Destroy every outstanding sandbox on leaving the sync context."""
        # See `SandboxProcess.__exit__`: forcing the sync branch is what keeps a
        # `with` block inside an async context from leaking every sandbox it made.
        try:
            self.close(_sync=True)
        except Exception:
            if exc_info and exc_info[0] is not None:
                self.logger.exception(
                    "Sandbox cleanup failed while handling another error."
                )
                return
            raise
