"""Tests for the `run_in_sandbox` / `run_python_in_sandbox` task entrypoints.

Two things are being checked here that a behavioural test alone would miss:

* that these are still real Prefect **Tasks** — `@task` has to be the outermost
  decorator, and getting it backwards silently reduces them to plain functions with no
  `.with_options()`, `.submit()` or `.map()` (a mistake several in-repo integrations
  currently ship); and
* that `run_python_in_sandbox` puts the *source* into the sandbox as a file rather than
  on a command line, so quotes, newlines and non-ASCII in generated code survive intact.

The `FakeSandbox` backend is reused from `test_operations.py` rather than duplicated —
`tests/` is on `sys.path` during collection because it holds no `__init__.py`.
"""

from __future__ import annotations

import base64
import logging
import shlex
from collections.abc import Sequence
from typing import Any

import pytest
from prefect_sandbox.base import (
    SANDBOX_NAME_PREFIX,
    Sandbox,
    SandboxBackend,
    SandboxExecutionError,
)
from prefect_sandbox.tasks import (
    PYTHON_SCRIPT_DIR,
    arun_in_sandbox,
    arun_python_in_sandbox,
    run_in_sandbox,
    run_python_in_sandbox,
)
from test_operations import FakeSandbox

from prefect import flow
from prefect.logging import disable_run_logger
from prefect.tasks import Task

#: Source that breaks every naive way of smuggling code into a sandbox: single and
#: double quotes, a backslash, an embedded newline, a shell metacharacter, and non-ASCII.
TRICKY_SOURCE = (
    "msg = 'it\\'s \"quoted\" & $PATH-ish'\n"
    'print(f"{msg}\\n→ ünïcödé ✅")\n'
    "print('''triple\nquoted''')\n"
)


class InlineWriteSandbox(FakeSandbox):
    """A `FakeSandbox` that keeps the base class's portable `awrite_file`.

    `FakeSandbox` overrides `awrite_file` with a native recording hook, the way a backend
    with a real file API does. This subclass restores the fallback in `base.py` — the one
    that base64-encodes the payload onto a command line — so a test can prove the source
    survives the trip a backend with no file API takes.
    """

    async def awrite_file(self, sandbox: Sandbox, path: str, content: str) -> None:
        """Delegate to the portable base implementation rather than recording."""
        await SandboxBackend.awrite_file(self, sandbox, path, content)


def decode_inline_write(command: Sequence[str]) -> str:
    """Recover the payload from a base64 inline-write script produced by `base.py`."""
    tokens = shlex.split(command[2])
    return base64.b64decode(tokens[tokens.index("printf") + 2]).decode()


class TestRunInSandbox:
    """`run_in_sandbox` and its async twin, as tasks and as plain callables."""

    def test_inside_a_sync_flow(self) -> None:
        backend = FakeSandbox(stdout="hello\nworld")

        @flow
        def sandbox_flow() -> list[str]:
            return run_in_sandbox(backend, ["echo hello", "echo world"])

        assert sandbox_flow() == ["hello", "world"]
        assert backend.live == set()
        assert backend.execs[0]["command"] == ["sh", "-c", "echo hello\necho world"]

    async def test_inside_an_async_flow(self) -> None:
        backend = FakeSandbox(stdout="hello")

        @flow
        async def sandbox_flow() -> list[str]:
            return await arun_in_sandbox(backend, ["echo hello"])

        assert await sandbox_flow() == ["hello"]
        assert backend.live == set()

    async def test_undecorated_function_without_a_run_context(self) -> None:
        backend = FakeSandbox(stdout="hello")

        with disable_run_logger():
            assert await arun_in_sandbox.fn(backend, ["echo hello"]) == ["hello"]

    def test_every_option_is_forwarded(self) -> None:
        backend = FakeSandbox(stdout="ok")

        @flow
        def sandbox_flow() -> list[str]:
            return run_in_sandbox(
                backend,
                ["cat data.txt"],
                env={"TOKEN": "abc"},
                working_dir="/work",
                shell="bash",
                timeout=12.5,
                files={"/work/data.txt": "payload"},
            )

        assert sandbox_flow() == ["ok"]
        assert backend.writes == [
            (backend.execs[0]["sandbox_id"], "/work/data.txt", "payload")
        ]
        call = backend.execs[0]
        assert call["command"] == ["bash", "-c", "cat data.txt"]
        assert call["env"] == {"TOKEN": "abc"}
        assert call["working_dir"] == "/work"
        assert call["timeout"] == 12.5
        assert backend.event_kinds == ["create", "write", "exec", "destroy"]

    def test_nonzero_exit_fails_the_flow(self) -> None:
        backend = FakeSandbox(exit_code=1, stderr="cat: data.txt: No such file")

        @flow
        def sandbox_flow() -> list[str]:
            return run_in_sandbox(backend, ["cat data.txt"])

        with pytest.raises(SandboxExecutionError, match="exit code 1"):
            sandbox_flow()

        # Failure still reclaims the sandbox.
        assert backend.live == set()

    def test_nonzero_exit_is_data_when_asked(self) -> None:
        backend = FakeSandbox(exit_code=1, stdout="partial output")

        @flow
        def sandbox_flow() -> list[str]:
            return run_in_sandbox(backend, ["cat data.txt"], raise_on_failure=False)

        assert sandbox_flow() == ["partial output"]

    async def test_output_reaches_the_task_run_logger(
        self, prefect_task_runs_caplog: pytest.LogCaptureFixture
    ) -> None:
        prefect_task_runs_caplog.set_level(logging.INFO)
        backend = FakeSandbox(stdout="streamed line", stderr="streamed error")

        @flow
        async def sandbox_flow() -> list[str]:
            return await arun_in_sandbox(backend, ["echo hi"])

        await sandbox_flow()

        assert "streamed line" in prefect_task_runs_caplog.text
        assert "streamed error" in prefect_task_runs_caplog.text

    async def test_stream_output_false_suppresses_the_output(
        self, prefect_task_runs_caplog: pytest.LogCaptureFixture
    ) -> None:
        prefect_task_runs_caplog.set_level(logging.INFO)
        backend = FakeSandbox(stdout="quiet please")

        @flow
        async def sandbox_flow() -> list[str]:
            return await arun_in_sandbox(backend, ["echo hi"], stream_output=False)

        assert await sandbox_flow() == ["quiet please"]
        assert "quiet please" not in prefect_task_runs_caplog.text


class TestRunPythonInSandbox:
    """`run_python_in_sandbox` writes the source in and then runs it."""

    def test_source_is_written_then_executed(self) -> None:
        backend = FakeSandbox(stdout="42")

        @flow
        def sandbox_flow() -> list[str]:
            return run_python_in_sandbox("print(6 * 7)", backend)

        assert sandbox_flow() == ["42"]

        assert backend.event_kinds == ["create", "write", "exec", "destroy"]
        _, path, content = backend.writes[0]
        assert content == "print(6 * 7)"
        assert path.startswith(f"{PYTHON_SCRIPT_DIR}/{SANDBOX_NAME_PREFIX}")
        assert path.endswith(".py")
        assert backend.execs[0]["command"] == ["sh", "-c", f"python {path}"]

    async def test_tricky_source_survives_verbatim(self) -> None:
        backend = FakeSandbox(stdout="ok")

        @flow
        async def sandbox_flow() -> list[str]:
            return await arun_python_in_sandbox(TRICKY_SOURCE, backend)

        assert await sandbox_flow() == ["ok"]
        assert backend.writes[0][2] == TRICKY_SOURCE
        # The source is nowhere near the command line, so nothing in it can be
        # reinterpreted by the shell.
        assert TRICKY_SOURCE not in backend.execs[0]["command"][2]

    async def test_tricky_source_survives_the_portable_inline_write(self) -> None:
        """Even the base64-on-the-command-line fallback must carry the bytes intact."""
        backend = InlineWriteSandbox(stdout="ok")

        with disable_run_logger():
            assert await arun_python_in_sandbox.fn(TRICKY_SOURCE, backend) == ["ok"]

        write_call, run_call = backend.execs
        assert decode_inline_write(write_call["command"]) == TRICKY_SOURCE
        script_path = run_call["command"][2].split(" ", 1)[1]
        assert script_path.endswith(".py")

    async def test_each_call_gets_its_own_script_path(self) -> None:
        backend = FakeSandbox(stdout="ok")

        with disable_run_logger():
            await arun_python_in_sandbox.fn("print(1)", backend)
            await arun_python_in_sandbox.fn("print(2)", backend)

        first, second = (path for _, path, _ in backend.writes)
        assert first != second

    async def test_python_executable_is_quoted(self) -> None:
        backend = FakeSandbox(stdout="ok")

        with disable_run_logger():
            await arun_python_in_sandbox.fn(
                "print(1)", backend, python_executable="/opt/my python/bin/python3"
            )

        script = backend.execs[0]["command"][2]
        assert script.startswith("'/opt/my python/bin/python3' ")

    async def test_options_are_forwarded(self) -> None:
        backend = FakeSandbox(stdout="ok")

        with disable_run_logger():
            await arun_python_in_sandbox.fn(
                "print(1)",
                backend,
                env={"PYTHONHASHSEED": "0"},
                working_dir="/srv",
                shell="bash",
                timeout=7.5,
            )

        call = backend.execs[0]
        assert call["command"][0] == "bash"
        assert call["env"] == {"PYTHONHASHSEED": "0"}
        assert call["working_dir"] == "/srv"
        assert call["timeout"] == 7.5

    def test_nonzero_exit_fails_the_flow(self) -> None:
        backend = FakeSandbox(exit_code=1, stderr="Traceback ... ZeroDivisionError")

        @flow
        def sandbox_flow() -> list[str]:
            return run_python_in_sandbox("1 / 0", backend)

        with pytest.raises(SandboxExecutionError, match="ZeroDivisionError"):
            sandbox_flow()

        assert backend.live == set()

    def test_nonzero_exit_is_data_when_asked(self) -> None:
        backend = FakeSandbox(exit_code=1, stdout="printed before crashing")

        @flow
        def sandbox_flow() -> list[str]:
            return run_python_in_sandbox("1 / 0", backend, raise_on_failure=False)

        assert sandbox_flow() == ["printed before crashing"]


class TestTaskIdentity:
    """`@task` must be the outermost decorator on all four entrypoints.

    Reversed, `async_dispatch` returns a plain function, `@task` never runs, and the
    result looks callable while quietly losing every Task affordance. That is a silent
    regression — hence a direct assertion rather than a behavioural one.
    """

    @pytest.mark.parametrize(
        "entrypoint",
        [
            run_in_sandbox,
            arun_in_sandbox,
            run_python_in_sandbox,
            arun_python_in_sandbox,
        ],
        ids=lambda task: task.name,
    )
    def test_is_a_prefect_task(self, entrypoint: Task[Any, Any]) -> None:
        assert isinstance(entrypoint, Task)

    @pytest.mark.parametrize(
        "entrypoint",
        [
            run_in_sandbox,
            arun_in_sandbox,
            run_python_in_sandbox,
            arun_python_in_sandbox,
        ],
        ids=lambda task: task.name,
    )
    def test_with_options_still_works(self, entrypoint: Task[Any, Any]) -> None:
        retried = entrypoint.with_options(retries=2, name="retried")

        assert isinstance(retried, Task)
        assert retried.retries == 2
        assert retried.name == "retried"
        assert callable(entrypoint.submit)
        assert callable(entrypoint.map)

    @pytest.mark.parametrize(
        ("sync_task", "async_task"),
        [
            (run_in_sandbox, arun_in_sandbox),
            (run_python_in_sandbox, arun_python_in_sandbox),
        ],
        ids=["commands", "python"],
    )
    def test_sync_task_carries_its_async_twin(
        self, sync_task: Task[Any, Any], async_task: Task[Any, Any]
    ) -> None:
        # `async_dispatch` hangs the async implementation off the sync wrapper as
        # `.aio`, and `@task` wraps that wrapper — so the pairing is observable.
        assert sync_task.fn.aio is async_task

    def test_names_keep_the_sandbox_qualifier(self) -> None:
        # `run_code` was the original name and it collided with an agent framework's
        # code-mode meta-tool; the qualifier is load-bearing, not decoration.
        assert run_python_in_sandbox.name == "run_python_in_sandbox"
        assert arun_python_in_sandbox.name == "arun_python_in_sandbox"
        assert run_in_sandbox.name == "run_in_sandbox"
        assert arun_in_sandbox.name == "arun_in_sandbox"

    async def test_submit_runs_the_task_through_the_engine(self) -> None:
        backend = FakeSandbox(stdout="submitted")

        @flow
        async def sandbox_flow() -> list[str]:
            future = arun_in_sandbox.submit(backend, ["echo hi"])
            return future.result()

        assert await sandbox_flow() == ["submitted"]
