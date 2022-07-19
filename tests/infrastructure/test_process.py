import os
import sys
from unittest.mock import MagicMock

import anyio
import anyio.abc
import pytest

from prefect.infrastructure.process import Process
from prefect.testing.utilities import AsyncMock


@pytest.fixture
def mock_open_process(monkeypatch):
    monkeypatch.setattr("anyio.open_process", AsyncMock())
    anyio.open_process.return_value.terminate = MagicMock()  #  Not an async attribute
    yield anyio.open_process


@pytest.mark.parametrize("stream_output", [True, False])
async def test_process_stream_output(capsys, stream_output):
    assert await Process(
        stream_output=stream_output, command=["echo", "hello world"]
    ).run()

    out, err = capsys.readouterr()

    if not stream_output:
        assert err == ""
        assert out == ""
    else:
        assert "hello world" in out


@pytest.mark.skipif(
    sys.platform == "win32", reason="stderr redirect does not work on Windows"
)
async def test_process_streams_stderr(capsys):
    assert await Process(
        command=["bash", "-c", ">&2 echo hello world"], stream_output=True
    ).run()

    out, err = capsys.readouterr()
    assert out == ""
    assert err.strip() == "hello world"


@pytest.mark.parametrize("exit_code", [0, 1, 2])
async def test_process_returns_exit_code(exit_code):
    result = await Process(command=["bash", "-c", f"exit {exit_code}"]).run()
    assert result.status_code == exit_code
    assert bool(result) is (exit_code == 0)


async def test_process_runs_command(tmp_path):
    # Perform a side-effect to demonstrate the command is run
    assert await Process(command=["touch", str(tmp_path / "canary")]).run()
    assert (tmp_path / "canary").exists()


async def test_process_cannot_be_run_with_empty_command():
    with pytest.raises(ValueError, match="cannot be run with empty command"):
        await Process().run()


async def test_process_environment_variables(monkeypatch, mock_open_process):
    monkeypatch.setenv("MYVAR", "VALUE")
    await Process(command=["echo", "hello"], stream_output=False).run()
    mock_open_process.assert_awaited_once()
    env = mock_open_process.call_args[1].get("env")
    assert env == {**os.environ, **Process._base_environment(), "MYVAR": "VALUE"}


async def test_process_includes_current_env_vars(monkeypatch, capsys):
    monkeypatch.setenv("MYVAR", "VALUE-A")
    assert await Process(command=["bash", "-c", "echo $MYVAR"]).run()
    out, _ = capsys.readouterr()
    assert "VALUE-A" in out


async def test_process_env_override_current_env_vars(monkeypatch, capsys):
    monkeypatch.setenv("MYVAR", "VALUE-A")
    assert await Process(
        command=["bash", "-c", "echo $MYVAR"], env={"MYVAR": "VALUE-B"}
    ).run()
    out, _ = capsys.readouterr()
    assert "VALUE-B" in out


async def test_process_created_then_marked_as_started(mock_open_process):
    fake_status = MagicMock(spec=anyio.abc.TaskStatus)
    # By raising an exception when started is called we can assert the process
    # is opened before this time
    fake_status.started.side_effect = RuntimeError("Started called!")

    with pytest.raises(RuntimeError, match="Started called!"):
        await Process(command=["echo", "hello"], stream_output=False).run(
            task_status=fake_status
        )

    fake_status.started.assert_called_once()
    mock_open_process.assert_awaited_once()


async def test_task_status_receives_pid():
    fake_status = MagicMock(spec=anyio.abc.TaskStatus)
    result = await Process(command=["echo", "hello"], stream_output=False).run(
        task_status=fake_status
    )
    fake_status.started.assert_called_once_with(result.identifier)
