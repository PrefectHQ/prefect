"""Prefect tasks for running commands and untrusted code inside a sandbox.

Each task is a thin wrapper over `SandboxOperation` rather than a second
implementation of it. `prefect_shell.shell_run_command` duplicates the whole of
`ShellOperation` and the two have drifted; there is one code path here.
"""

from __future__ import annotations

import shlex
from collections.abc import Mapping, Sequence

from prefect import task
from prefect._internal.compatibility.async_dispatch import async_dispatch
from prefect_sandbox.base import SandboxBackend, new_sandbox_name
from prefect_sandbox.operations import DEFAULT_TIMEOUT_SECONDS, SandboxOperation

__all__ = [
    "arun_in_sandbox",
    "arun_python_in_sandbox",
    "run_in_sandbox",
    "run_python_in_sandbox",
]

#: Directory inside the sandbox that `run_python_in_sandbox` writes its script to.
#: `/tmp` is the one path a slim image is guaranteed to have and to be writable.
PYTHON_SCRIPT_DIR = "/tmp"


def _build_operation(
    backend: SandboxBackend,
    commands: Sequence[str],
    *,
    env: Mapping[str, str] | None,
    working_dir: str | None,
    shell: str,
    timeout: float,
    files: Mapping[str, str] | None,
    stream_output: bool,
    raise_on_failure: bool,
) -> SandboxOperation:
    """Build the operation both twins of `run_in_sandbox` delegate to."""
    return SandboxOperation(
        backend,
        commands,
        env=env,
        working_dir=working_dir,
        shell=shell,
        timeout=timeout,
        files=files,
        stream_output=stream_output,
        raise_on_failure=raise_on_failure,
    )


def _build_python_operation(
    code: str,
    backend: SandboxBackend,
    *,
    python_executable: str,
    env: Mapping[str, str] | None,
    working_dir: str | None,
    shell: str,
    timeout: float,
    stream_output: bool,
    raise_on_failure: bool,
) -> SandboxOperation:
    """Build the operation both twins of `run_python_in_sandbox` delegate to.

    The source travels in through `SandboxBackend.awrite_file` instead of `python -c`,
    so newlines, quotes and non-ASCII in generated code cannot corrupt the command line
    and tracebacks name a real file with real line numbers.
    """
    script_path = f"{PYTHON_SCRIPT_DIR}/{new_sandbox_name()}.py"
    return _build_operation(
        backend,
        [f"{shlex.quote(python_executable)} {shlex.quote(script_path)}"],
        env=env,
        working_dir=working_dir,
        shell=shell,
        timeout=timeout,
        files={script_path: code},
        stream_output=stream_output,
        raise_on_failure=raise_on_failure,
    )


@task
async def arun_in_sandbox(
    backend: SandboxBackend,
    commands: Sequence[str],
    env: Mapping[str, str] | None = None,
    working_dir: str | None = None,
    shell: str = "sh",
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    files: Mapping[str, str] | None = None,
    stream_output: bool = True,
    raise_on_failure: bool = True,
) -> list[str]:
    """Run commands in a fresh sandbox that is destroyed afterwards (async version).

    Args:
        backend: The sandbox provider to run in.
        commands: Commands to execute sequentially in one shell inside the sandbox.
        env: Environment variables to set. Nothing is inherited from the worker.
        working_dir: Directory inside the sandbox to run in.
        shell: Shell to interpret `commands` with.
        timeout: Seconds the commands may run before the backend stops them.
        files: Files to write into the sandbox first, as `{path: content}`.
        stream_output: Whether to relay captured output to the run logger.
        raise_on_failure: Whether a nonzero exit raises `SandboxExecutionError`.

    Returns:
        The stdout lines produced by the commands.

    Example:
        ```python
        from prefect import flow
        from prefect_sandbox import SbxSandbox, arun_in_sandbox

        @flow
        async def example_flow():
            return await arun_in_sandbox(SbxSandbox(), ["echo hello"])
        ```
    """
    return await _build_operation(
        backend,
        commands,
        env=env,
        working_dir=working_dir,
        shell=shell,
        timeout=timeout,
        files=files,
        stream_output=stream_output,
        raise_on_failure=raise_on_failure,
    ).arun()


# `@task` must be the OUTERMOST decorator. Reversed, the result is a plain function and
# Task identity — `.with_options()`, `.submit()`, `.map()` — silently vanishes; several
# in-repo integrations (prefect-aws `s3.py`, `batch.py`, `client_waiter.py`) still get
# this backwards. A consequence of the correct order: `Task.isasync` is read off the
# sync wrapper, so the dispatcher always resolves to the sync branch once inside this
# task's run context. That is why `arun_in_sandbox` exists as its own async task rather
# than being reachable through this one.
@task
@async_dispatch(arun_in_sandbox)
def run_in_sandbox(
    backend: SandboxBackend,
    commands: Sequence[str],
    env: Mapping[str, str] | None = None,
    working_dir: str | None = None,
    shell: str = "sh",
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    files: Mapping[str, str] | None = None,
    stream_output: bool = True,
    raise_on_failure: bool = True,
) -> list[str]:
    """Run commands in a fresh sandbox that is destroyed afterwards (sync version).

    Args:
        backend: The sandbox provider to run in.
        commands: Commands to execute sequentially in one shell inside the sandbox.
        env: Environment variables to set. Nothing is inherited from the worker.
        working_dir: Directory inside the sandbox to run in.
        shell: Shell to interpret `commands` with.
        timeout: Seconds the commands may run before the backend stops them.
        files: Files to write into the sandbox first, as `{path: content}`.
        stream_output: Whether to relay captured output to the run logger.
        raise_on_failure: Whether a nonzero exit raises `SandboxExecutionError`.

    Returns:
        The stdout lines produced by the commands.

    Example:
        ```python
        from prefect import flow
        from prefect_sandbox import SbxSandbox, run_in_sandbox

        @flow
        def example_flow():
            return run_in_sandbox(SbxSandbox(), ["echo hello"])
        ```
    """
    return _build_operation(
        backend,
        commands,
        env=env,
        working_dir=working_dir,
        shell=shell,
        timeout=timeout,
        files=files,
        stream_output=stream_output,
        raise_on_failure=raise_on_failure,
        # `_sync=True` pins the lane explicitly instead of letting the operation
        # re-inspect the context: this task body is only ever reached synchronously.
    ).run(_sync=True)


@task
async def arun_python_in_sandbox(
    code: str,
    backend: SandboxBackend,
    python_executable: str = "python",
    env: Mapping[str, str] | None = None,
    working_dir: str | None = None,
    shell: str = "sh",
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    stream_output: bool = True,
    raise_on_failure: bool = True,
) -> list[str]:
    """Execute Python source in a fresh sandbox that is destroyed afterwards (async version).

    The intended use is code you did not author — model-generated scripts, a user's
    snippet — which is exactly why it does not run on the worker.

    Args:
        code: Python source to execute. Written into the sandbox as a file, so it may
            contain anything a `.py` file may contain.
        backend: The sandbox provider to run in.
        python_executable: Interpreter to invoke inside the sandbox.
        env: Environment variables to set. Nothing is inherited from the worker.
        working_dir: Directory inside the sandbox to run in.
        shell: Shell used to invoke the interpreter.
        timeout: Seconds the script may run before the backend stops it.
        stream_output: Whether to relay captured output to the run logger.
        raise_on_failure: Whether a nonzero exit raises `SandboxExecutionError`.

    Returns:
        The stdout lines produced by the script.

    Example:
        ```python
        from prefect import flow
        from prefect_sandbox import SbxSandbox, arun_python_in_sandbox

        @flow
        async def example_flow(generated: str):
            return await arun_python_in_sandbox(generated, SbxSandbox())
        ```
    """
    return await _build_python_operation(
        code,
        backend,
        python_executable=python_executable,
        env=env,
        working_dir=working_dir,
        shell=shell,
        timeout=timeout,
        stream_output=stream_output,
        raise_on_failure=raise_on_failure,
    ).arun()


# Named `run_python_in_sandbox`, not `run_code`: in an earlier port of this integration
# the shorter name shadowed an agent framework's code-mode meta-tool and the two became
# impossible to tell apart in a tool listing. Keep the qualifier.
@task
@async_dispatch(arun_python_in_sandbox)
def run_python_in_sandbox(
    code: str,
    backend: SandboxBackend,
    python_executable: str = "python",
    env: Mapping[str, str] | None = None,
    working_dir: str | None = None,
    shell: str = "sh",
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    stream_output: bool = True,
    raise_on_failure: bool = True,
) -> list[str]:
    """Execute Python source in a fresh sandbox that is destroyed afterwards (sync version).

    Args:
        code: Python source to execute. Written into the sandbox as a file, so it may
            contain anything a `.py` file may contain.
        backend: The sandbox provider to run in.
        python_executable: Interpreter to invoke inside the sandbox.
        env: Environment variables to set. Nothing is inherited from the worker.
        working_dir: Directory inside the sandbox to run in.
        shell: Shell used to invoke the interpreter.
        timeout: Seconds the script may run before the backend stops it.
        stream_output: Whether to relay captured output to the run logger.
        raise_on_failure: Whether a nonzero exit raises `SandboxExecutionError`.

    Returns:
        The stdout lines produced by the script.

    Example:
        ```python
        from prefect import flow
        from prefect_sandbox import SbxSandbox, run_python_in_sandbox

        @flow
        def example_flow(generated: str):
            return run_python_in_sandbox(generated, SbxSandbox())
        ```
    """
    return _build_python_operation(
        code,
        backend,
        python_executable=python_executable,
        env=env,
        working_dir=working_dir,
        shell=shell,
        timeout=timeout,
        stream_output=stream_output,
        raise_on_failure=raise_on_failure,
    ).run(_sync=True)
