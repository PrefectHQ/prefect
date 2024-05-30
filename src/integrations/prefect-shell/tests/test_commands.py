import logging
import os
import sys
from pathlib import Path
from typing import Any, AsyncGenerator, Literal

import pytest
from prefect_shell.commands import ShellOperation, shell_run_command

from prefect import flow  # type: ignore
from prefect.testing.utilities import AsyncMock

if sys.platform == "win32":
    pytest.skip(reason="see test_commands_windows.py", allow_module_level=True)


def test_shell_run_command_error(prefect_task_runs_caplog: pytest.LogCaptureFixture):
    @flow
    def test_flow():
        return shell_run_command(command="ls this/is/invalid")

    match = "No such file or directory"
    with pytest.raises(RuntimeError, match=match):
        test_flow()  # type: ignore


def test_shell_run_command(prefect_task_runs_caplog: pytest.LogCaptureFixture):
    prefect_task_runs_caplog.set_level(logging.INFO)
    echo_msg = "_THIS_ IS WORKING!!!!"

    @flow
    def test_flow():
        return shell_run_command(command=f"echo {echo_msg}")

    test_flow()
    assert test_flow() == echo_msg
    assert echo_msg in prefect_task_runs_caplog.text


def test_shell_run_command_stream_level(
    prefect_task_runs_caplog: pytest.LogCaptureFixture,
):
    prefect_task_runs_caplog.set_level(logging.WARNING)
    echo_msg = "_THIS_ IS WORKING!!!!"

    @flow
    def test_flow():
        return shell_run_command(
            command=f"echo {echo_msg}",
            stream_level=logging.WARNING,
        )

    assert test_flow() == echo_msg
    assert echo_msg in prefect_task_runs_caplog.text


def test_shell_run_command_helper_command():
    @flow
    def test_flow():
        return shell_run_command(command="pwd", helper_command="cd $HOME")

    assert test_flow() == os.path.expandvars("$HOME")


def test_shell_run_command_cwd():
    @flow
    def test_flow():
        return shell_run_command(command="pwd", cwd=Path.home())

    assert test_flow() == os.fspath(Path.home())


def test_shell_run_command_return_all():
    @flow
    def test_flow():
        return shell_run_command(command="echo work! && echo yes!", return_all=True)

    assert test_flow() == ["work!", "yes!"]


def test_shell_run_command_no_output():
    @flow
    def test_flow():
        return shell_run_command(command="sleep 1")

    assert test_flow() == ""


def test_shell_run_command_uses_current_env():
    @flow
    def test_flow():
        return shell_run_command(command="echo $HOME")

    assert test_flow() == os.environ["HOME"]


def test_shell_run_command_update_current_env():
    @flow
    def test_flow():
        return shell_run_command(
            command="echo $HOME && echo $TEST_VAR",
            env={"TEST_VAR": "test value"},
            return_all=True,
        )

    result = test_flow()
    assert result[0] == os.environ["HOME"]  # type: ignore
    assert result[1] == "test value"  # type: ignore


class AsyncIter:
    def __init__(self, items: list[Any]):
        self.items = items

    async def __aiter__(self) -> AsyncGenerator[Any, Any]:
        for item in self.items:
            yield item


@pytest.mark.parametrize("shell", [None, "bash", "zsh"])
def test_shell_run_command_override_shell(
    shell: None | Literal["bash"] | Literal["zsh"], monkeypatch: pytest.MonkeyPatch
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
    def test_flow():
        return shell_run_command(
            command="echo 'testing'",
            shell=shell,
        )

    test_flow()
    assert open_process_mock.call_args_list[0][0][0][0] == shell or "bash"


class TestShellOperation:
    async def execute(self, op: ShellOperation, method: Literal["run", "trigger"]):
        if method == "run":
            return await op.run()
        elif method == "trigger":
            proc = await op.trigger()
            await proc.wait_for_completion()
            return await proc.fetch_result()

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_error(self, method: Literal["run"] | Literal["trigger"]):
        op = ShellOperation(commands=["ls this/is/invalid"])
        with pytest.raises(RuntimeError, match="return code"):
            await self.execute(op, method)

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_output(
        self,
        prefect_task_runs_caplog: pytest.LogCaptureFixture,
        method: Literal["run"] | Literal["trigger"],
    ):
        op = ShellOperation(commands=["echo 'testing\nthe output'", "echo good"])
        assert await self.execute(op, method) == ["testing", "the output", "good"]
        records = prefect_task_runs_caplog.records
        assert len(records) == 3
        assert "triggered with 2 commands running" in records[0].message
        assert "stream output:\ntesting\nthe output\ngood" in records[1].message
        assert "completed with return code 0" in records[2].message

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_stream_output(
        self,
        prefect_task_runs_caplog: pytest.LogCaptureFixture,
        method: Literal["run"] | Literal["trigger"],
    ):
        # If stream_output is False, there should be output,
        # but no logs from the shell process
        op = ShellOperation(
            commands=["echo 'testing\nthe output'", "echo good"], stream_output=False
        )
        assert await self.execute(op, method) == ["testing", "the output", "good"]
        records = prefect_task_runs_caplog.records
        assert len(records) == 2
        assert "triggered with 2 commands running" in records[0].message
        assert "completed with return code 0" in records[1].message

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_current_env(self, method: Literal["run"] | Literal["trigger"]):
        op = ShellOperation(commands=["echo $HOME"])
        assert await self.execute(op, method) == [os.environ["HOME"]]

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_updated_env(self, method: Literal["run"] | Literal["trigger"]):
        op = ShellOperation(commands=["echo $HOME"], env={"HOME": "test_home"})
        assert await self.execute(op, method) == ["test_home"]

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_cwd(self, method: Literal["run"] | Literal["trigger"]):
        op = ShellOperation(commands=["pwd"], working_dir=Path.home())
        assert await self.execute(op, method) == [os.fspath(Path.home())]

    @pytest.mark.parametrize("method", ["run", "trigger"])
    @pytest.mark.parametrize("shell", [None, "bash", "zsh", "BASH", "ZSH"])
    async def test_updated_shell(
        self,
        monkeypatch: pytest.MonkeyPatch,
        method: Literal["run"] | Literal["trigger"],
        shell: (
            None | Literal["bash"] | Literal["zsh"] | Literal["BASH"] | Literal["ZSH"]
        ),
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
        self,
        monkeypatch: pytest.MonkeyPatch,
        method: Literal["run"] | Literal["trigger"],
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

    def test_context_manager(self):
        with ShellOperation(commands=["echo 'testing'"]) as op:
            proc = op.trigger()
            proc.wait_for_completion()  # type: ignore
            assert proc.fetch_result() == ["testing"]  # type: ignore

    async def test_async_context_manager(self):
        async with ShellOperation(commands=["echo 'testing'"]) as op:
            proc = await op.trigger()
            await proc.wait_for_completion()
            assert await proc.fetch_result() == ["testing"]
