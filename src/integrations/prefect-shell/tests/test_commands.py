import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Union
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from prefect_shell.commands import ShellOperation, shell_run_command

from prefect import flow
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import LogFilter, LogFilterFlowRunId
from prefect.context import get_run_context
from prefect.logging.handlers import APILogHandler
from prefect.settings import PREFECT_LOGGING_TO_API_ENABLED, temporary_settings

if sys.platform == "win32":
    pytest.skip(reason="see test_commands_windows.py", allow_module_level=True)


async def wait_for_flow_run_logs(
    flow_run_id: UUID, expected_count: int
) -> list[object]:
    for _ in range(30):
        async with get_client() as client:
            logs = await client.read_logs(
                log_filter=LogFilter(
                    flow_run_id=LogFilterFlowRunId(any_=[flow_run_id]),
                )
            )
        if len(logs) >= expected_count:
            return logs
        await asyncio.sleep(0.1)

    return logs


@pytest.mark.usefixtures("prefect_task_runs_caplog")
async def test_shell_run_command_error():
    @flow
    async def test_flow():
        return await shell_run_command(command="ls this/is/invalid")

    match = "No such file or directory"
    with pytest.raises(RuntimeError, match=match):
        await test_flow()


async def test_shell_run_command(prefect_task_runs_caplog: pytest.LogCaptureFixture):
    prefect_task_runs_caplog.set_level(logging.INFO)
    echo_msg = "_THIS_ IS WORKING!!!!"

    @flow
    async def test_flow():
        return await shell_run_command(command=f"echo {echo_msg}")

    assert (await test_flow()) == echo_msg
    assert echo_msg in prefect_task_runs_caplog.text


async def test_shell_run_command_stream_level(
    prefect_task_runs_caplog: pytest.LogCaptureFixture,
):
    prefect_task_runs_caplog.set_level(logging.WARNING)
    echo_msg = "_THIS_ IS WORKING!!!!"

    @flow
    async def test_flow() -> Union[list[str], str]:
        return await shell_run_command(
            command=f"echo {echo_msg}",
            stream_level=logging.WARNING,
        )

    assert (await test_flow()) == echo_msg
    assert echo_msg in prefect_task_runs_caplog.text


async def test_shell_run_command_helper_command():
    @flow
    async def test_flow() -> Union[list[str], str]:
        return await shell_run_command(command="pwd", helper_command="cd $HOME")

    assert (await test_flow()) == os.path.expandvars("$HOME")


async def test_shell_run_command_cwd():
    @flow
    async def test_flow() -> Union[list[str], str]:
        return await shell_run_command(command="pwd", cwd=Path.home())

    assert (await test_flow()) == os.fspath(Path.home())


async def test_shell_run_command_return_all():
    @flow
    async def test_flow() -> Union[list[str], str]:
        return await shell_run_command(
            command="echo work! && echo yes!", return_all=True
        )

    assert (await test_flow()) == ["work!", "yes!"]


async def test_shell_run_command_no_output():
    @flow
    async def test_flow() -> Union[list[str], str]:
        return await shell_run_command(command="sleep 1")

    assert (await test_flow()) == ""


async def test_shell_run_command_uses_current_env():
    @flow
    async def test_flow() -> Union[list[str], str]:
        return await shell_run_command(command="echo $HOME")

    assert (await test_flow()) == os.environ["HOME"]


async def test_shell_run_command_update_current_env():
    @flow
    async def test_flow() -> Union[list[str], str]:
        return await shell_run_command(
            command="echo $HOME && echo $TEST_VAR",
            env={"TEST_VAR": "test value"},
            return_all=True,
        )

    result = await test_flow()
    assert result[0] == os.environ["HOME"]
    assert result[1] == "test value"


class AsyncIter:
    def __init__(self, items: list[str]):
        self.items = items

    async def __aiter__(self):
        for item in self.items:
            yield item


@pytest.mark.parametrize("shell", [None, "bash", "zsh"])
async def test_shell_run_command_override_shell(
    shell: Union[str, None], monkeypatch: pytest.MonkeyPatch
):
    open_process_mock = AsyncMock()
    stdout_mock = AsyncMock()
    stdout_mock.receive.side_effect = lambda: b"received"
    open_process_mock.return_value.__aenter__.return_value = AsyncMock(
        stdout=stdout_mock
    )
    open_process_mock.return_value.__aenter__.return_value.returncode = 0
    monkeypatch.setattr("anyio.open_process", open_process_mock)
    monkeypatch.setattr("prefect_shell.commands.TextReceiveStream", AsyncIter)

    @flow
    async def test_flow() -> Union[list[str], str]:
        return await shell_run_command(
            command="echo 'testing'",
            shell=shell,
        )

    await test_flow()
    assert open_process_mock.call_args_list[0][0][0][0] == shell or "bash"


class TestShellOperation:
    async def execute(
        self, op: ShellOperation, method: str
    ) -> Union[list[str], str, None]:
        if method == "run":
            return await op.run()
        elif method == "trigger":
            proc = await op.trigger()
            await proc.wait_for_completion()
            return await proc.fetch_result()

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_error(self, method: str):
        op = ShellOperation(commands=["ls this/is/invalid"])
        with pytest.raises(RuntimeError, match="return code"):
            await self.execute(op, method)

    @pytest.mark.skipif(sys.version >= "3.12", reason="Fails on Python 3.12")
    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_output(
        self, prefect_task_runs_caplog: pytest.LogCaptureFixture, method: str
    ):
        # Set the log level to INFO explicitly
        prefect_task_runs_caplog.set_level(logging.INFO)

        op = ShellOperation(commands=["echo 'testing\nthe output'", "echo good"])
        assert await self.execute(op, method) == ["testing", "the output", "good"]

        # Filter for only INFO-level shell logs
        log_messages = [
            r.message
            for r in prefect_task_runs_caplog.records
            if r.levelno >= logging.INFO
            and r.name in {"prefect.ShellOperation", "prefect.ShellProcess"}
        ]
        stream_messages = [m for m in log_messages if "stream output:" in m]
        assert any("triggered with 2 commands running" in m for m in log_messages)
        assert any("testing" in m for m in stream_messages)
        assert any("the output" in m for m in stream_messages)
        assert any("good" in m for m in stream_messages)
        assert any("completed with return code 0" in m for m in log_messages)

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_stream_output(
        self, prefect_task_runs_caplog: pytest.LogCaptureFixture, method: str
    ):
        # If stream_output is False, there should be output,
        # but no logs from the shell process
        prefect_task_runs_caplog.set_level(logging.INFO)  # Only capture INFO logs

        op = ShellOperation(
            commands=["echo 'testing\nthe output'", "echo good"], stream_output=False
        )
        assert await self.execute(op, method) == ["testing", "the output", "good"]
        records = [
            r
            for r in prefect_task_runs_caplog.records
            if r.levelno >= logging.INFO
            and r.name in {"prefect.ShellOperation", "prefect.ShellProcess"}
        ]
        assert len(records) == 2
        assert any("triggered with 2 commands running" in r.message for r in records)
        assert any("completed with return code 0" in r.message for r in records)

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_current_env(self, method: str):
        op = ShellOperation(commands=["echo $HOME"])
        assert await self.execute(op, method) == [os.environ["HOME"]]

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_updated_env(self, method: str):
        op = ShellOperation(commands=["echo $HOME"], env={"HOME": "test_home"})
        assert await self.execute(op, method) == ["test_home"]

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_cwd(self, method: str):
        op = ShellOperation(commands=["pwd"], working_dir=Path.home())
        assert await self.execute(op, method) == [os.fspath(Path.home())]

    @pytest.mark.parametrize("method", ["run", "trigger"])
    @pytest.mark.parametrize("shell", [None, "bash", "zsh", "BASH", "ZSH"])
    async def test_updated_shell(
        self, monkeypatch: pytest.MonkeyPatch, method: str, shell: Union[str, None]
    ):
        open_process_mock = AsyncMock(name="open_process")
        stdout_mock = AsyncMock(name="stdout_mock")
        stdout_mock.receive.side_effect = lambda: b"received"
        open_process_mock.return_value.__aenter__.return_value = AsyncMock(
            stdout=stdout_mock
        )
        open_process_mock.return_value.returncode = 0
        monkeypatch.setattr("anyio.open_process", open_process_mock)
        monkeypatch.setattr("prefect_shell.commands.TextReceiveStream", AsyncIter)

        op = ShellOperation(commands=["pwd"], shell=shell, working_dir=Path.home())
        await self.execute(op, method)
        assert open_process_mock.call_args_list[0][0][0][0] == (shell or "bash").lower()

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_select_powershell(
        self, monkeypatch: pytest.MonkeyPatch, method: str
    ):
        open_process_mock = AsyncMock(name="open_process")
        stdout_mock = AsyncMock(name="stdout_mock")
        stdout_mock.receive.side_effect = lambda: b"received"
        open_process_mock.return_value.__aenter__.return_value = AsyncMock(
            stdout=stdout_mock
        )
        open_process_mock.return_value.returncode = 0
        monkeypatch.setattr("anyio.open_process", open_process_mock)
        monkeypatch.setattr("prefect_shell.commands.TextReceiveStream", AsyncIter)

        await self.execute(
            ShellOperation(commands=["echo 'hey'"], extension=".ps1"), method
        )
        assert open_process_mock.call_args_list[0][0][0][0] == "powershell"

    async def test_context_manager(self):
        async with ShellOperation(commands=["echo 'testing'"]) as op:
            proc = await op.trigger()
            await proc.wait_for_completion()
            await proc.fetch_result() == ["testing"]

    def test_sync_context_manager(self):
        with ShellOperation(commands=["echo 'testing'"]) as op:
            proc = op.trigger()
            proc.wait_for_completion()
            proc.fetch_result() == ["testing"]

    def test_sync_streaming_output(
        self, prefect_task_runs_caplog: pytest.LogCaptureFixture
    ):
        """Regression test for https://github.com/PrefectHQ/prefect/issues/20680.

        Verifies that sync wait_for_completion streams output line-by-line
        rather than buffering all output until the process exits.
        With the old communicate()-based implementation, all output was
        emitted as a single log record after the process completed.
        """
        prefect_task_runs_caplog.set_level(logging.INFO)

        with ShellOperation(commands=["echo line1", "echo line2", "echo line3"]) as op:
            proc = op.trigger()
            proc.wait_for_completion()
            result = proc.fetch_result()

        assert result == ["line1", "line2", "line3"]

        stream_records = [
            r
            for r in prefect_task_runs_caplog.records
            if r.levelno >= logging.INFO and "stream output" in r.message
        ]
        assert len(stream_records) == 3, (
            "Each line should produce its own log record (not one buffered record)"
        )
        assert "line1" in stream_records[0].message
        assert "line2" in stream_records[1].message
        assert "line3" in stream_records[2].message

    def test_sync_streaming_stderr_output(
        self, prefect_task_runs_caplog: pytest.LogCaptureFixture
    ):
        prefect_task_runs_caplog.set_level(logging.INFO)

        with ShellOperation(
            commands=["echo out1", "echo err1 >&2", "echo out2", "echo err2 >&2"]
        ) as op:
            proc = op.trigger()
            proc.wait_for_completion()
            result = proc.fetch_result()

        assert result == ["out1", "out2"]

        stream_records = [
            r
            for r in prefect_task_runs_caplog.records
            if r.levelno >= logging.INFO and "stream output" in r.message
        ]
        stderr_records = [
            r
            for r in prefect_task_runs_caplog.records
            if r.levelno >= logging.INFO and "stderr" in r.message
        ]

        assert len(stream_records) == 2
        assert len(stderr_records) == 2
        assert any("out1" in r.message for r in stream_records)
        assert any("out2" in r.message for r in stream_records)
        assert any("err1" in r.message for r in stderr_records)
        assert any("err2" in r.message for r in stderr_records)

    async def test_sync_streaming_output_is_sent_to_api(self):
        with temporary_settings(updates={PREFECT_LOGGING_TO_API_ENABLED: True}):

            @flow
            def test_flow() -> UUID:
                ShellOperation(
                    commands=[
                        "echo out1",
                        "echo err1 >&2",
                        "echo out2",
                        "echo err2 >&2",
                    ]
                ).run()
                return get_run_context().flow_run.id

            flow_run_id = test_flow()
            await APILogHandler.aflush()
            logs = await wait_for_flow_run_logs(flow_run_id, expected_count=6)

        messages = {log.message for log in logs}
        assert any(
            "PID" in message and "stream output:" in message for message in messages
        )
        assert any("out1" in message for message in messages)
        assert any("out2" in message for message in messages)
        assert any("PID" in message and "stderr:" in message for message in messages)
        assert any("err1" in message for message in messages)
        assert any("err2" in message for message in messages)


class TestShellOperationProcessGroup:
    """Tests that ShellOperation subprocesses are isolated in their own process
    group so that cleanup kills the whole process tree, not just the shell
    (see GH #20979)."""

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            return False
        return True

    async def test_async_subprocess_is_own_session_leader(self, tmp_path: Path):
        """The spawned shell should be a session leader so its whole process
        tree can be signalled together."""
        op = ShellOperation(commands=["sleep 30"])
        async with op:
            proc = await op.atrigger()
            try:
                assert os.getsid(proc.pid) == proc.pid, (
                    f"Expected subprocess {proc.pid} to be its own session leader; "
                    f"got sid={os.getsid(proc.pid)}"
                )
            finally:
                proc._process.terminate()
                await proc._process.wait()

    def test_sync_subprocess_is_own_session_leader(self):
        """The sync `trigger()` path should also place the shell in a new session."""
        op = ShellOperation(commands=["sleep 30"])
        with op:
            proc = op.trigger()
            try:
                assert os.getsid(proc.pid) == proc.pid, (
                    f"Expected subprocess {proc.pid} to be its own session leader; "
                    f"got sid={os.getsid(proc.pid)}"
                )
            finally:
                proc._process.kill()
                proc._process.wait()

    async def test_aclose_terminates_descendant_processes(self, tmp_path: Path):
        """Closing the operation must terminate any descendants the shell spawned,
        not just the direct shell process (regression for GH #20979)."""
        pid_file = tmp_path / "child.pid"
        op = ShellOperation(
            commands=[f"sleep 120 & echo $! > {pid_file}; wait"],
        )
        async with op:
            proc = await op.atrigger()

            # Wait for the inner `sleep` to spawn and record its PID.
            for _ in range(50):
                if pid_file.exists() and pid_file.read_text().strip():
                    break
                await asyncio.sleep(0.1)
            else:
                proc._process.terminate()
                pytest.fail("inner sleep process did not start in time")

            child_pid = int(pid_file.read_text().strip())
            assert self._pid_alive(child_pid), "sleep process should be running"

        # After exiting the context, the shell's descendants must be gone.
        for _ in range(50):
            if not self._pid_alive(child_pid):
                break
            await asyncio.sleep(0.1)
        assert not self._pid_alive(child_pid), (
            f"inner sleep (pid={child_pid}) was orphaned after aclose()"
        )

    def test_sync_close_terminates_descendant_processes(self, tmp_path: Path):
        """Exiting the sync context manager after `trigger()` must terminate the
        shell's descendants, not just the shell itself (regression for GH #20979).
        """
        import time as _time

        pid_file = tmp_path / "child.pid"
        op = ShellOperation(
            commands=[f"sleep 120 & echo $! > {pid_file}; wait"],
        )
        with op:
            op.trigger()
            for _ in range(50):
                if pid_file.exists() and pid_file.read_text().strip():
                    break
                _time.sleep(0.1)
            else:
                pytest.fail("inner sleep process did not start in time")

            child_pid = int(pid_file.read_text().strip())
            assert self._pid_alive(child_pid), "sleep process should be running"

        # After exiting the context manager, `close()` must have reclaimed the
        # full process tree, not just the shell.
        for _ in range(50):
            if not self._pid_alive(child_pid):
                break
            _time.sleep(0.1)
        assert not self._pid_alive(child_pid), (
            f"inner sleep (pid={child_pid}) was orphaned after context exit"
        )
