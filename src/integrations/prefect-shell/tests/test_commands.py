import logging
import os
import sys
from pathlib import Path
from typing import Union

import pytest
from prefect_shell.commands import ShellOperation, shell_run_command

from prefect import flow
from prefect.testing.utilities import AsyncMock

if sys.platform == "win32":
    pytest.skip(reason="see test_commands_windows.py", allow_module_level=True)


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

        # Filter for only INFO level records
        log_messages = [
            r.message
            for r in prefect_task_runs_caplog.records
            if r.levelno >= logging.INFO
        ]
        assert any("triggered with 2 commands running" in m for m in log_messages)
        assert any(
            "stream output:\ntesting\nthe output\ngood" in m for m in log_messages
        )
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
            r for r in prefect_task_runs_caplog.records if r.levelno >= logging.INFO
        ]
        assert len(records) == 2
        assert "triggered with 2 commands running" in records[0].message
        assert "completed with return code 0" in records[1].message

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
