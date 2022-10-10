import os
import signal
import subprocess
import sys
from unittest import mock

import anyio
import anyio.abc
import psutil
import pytest

from prefect.testing.utilities import AsyncMock
from prefect.utilities.processutils import (
    kill_on_interrupt,
    open_process,
    run_process,
    stop_process,
)


@pytest.fixture
def mock_open_process(monkeypatch):
    monkeypatch.setattr("anyio.open_process", AsyncMock())
    anyio.open_process.return_value = AsyncMock(spec=anyio.abc.Process, pid=123456)
    yield anyio.open_process


async def test_open_process_with_defaults(mock_open_process):
    await open_process(["echo", "hello world"])
    mock_open_process.assert_awaited_once()

    kwargs = mock_open_process.call_args[1]
    assert "stdout" in kwargs
    assert kwargs["stdout"] == subprocess.DEVNULL
    assert "stderr" in kwargs
    assert kwargs["stderr"] == subprocess.DEVNULL


async def test_open_process_with_kwargs(mock_open_process):
    await open_process(["echo", "hello world"], env={"test_kwarg": "test_kwarg"})
    mock_open_process.assert_awaited_once()

    kwargs = mock_open_process.call_args[1]
    assert "env" in kwargs
    assert kwargs["env"] == {"test_kwarg": "test_kwarg"}


async def test_open_process_with_pid_file(tmp_path, mock_open_process):
    pid_file = tmp_path / "test.pid"
    assert os.path.exists(pid_file) is False

    process = await open_process(["echo", "hello world"], pid_file=pid_file)
    mock_open_process.assert_awaited_once()
    assert process.pid == 123456
    assert os.path.exists(pid_file) is True

    with open(pid_file, "r") as f:
        process_pid = f.read()
    assert str(process.pid) == process_pid


async def test_open_process_with_invalid_command(mock_open_process):
    mock_open_process.side_effect = OSError("No such file or directory: command")

    with pytest.raises(OSError, match="No such file or directory: command"):
        await open_process(["test_invalid_command"])

    mock_open_process.assert_awaited_once()


async def test_open_process_with_invalid_pid_file(monkeypatch, mock_open_process):
    mock_open = mock.mock_open()
    mock_open.side_effect = OSError("monk_open error")
    monkeypatch.setattr("builtins.open", mock_open)

    with pytest.raises(
        OSError, match="Could not write PID to file 'path/to/pid_file': monk_open error"
    ):
        await open_process(["echo", "hello world"], pid_file="path/to/pid_file")

    mock_open_process.assert_awaited_once()
    mock_open_process.return_value.terminate.assert_called_once()
    mock_open_process.return_value.wait.assert_awaited_once()


async def test_run_process_with_defaults(mock_open_process):
    await run_process(["echo", "hello world"])
    mock_open_process.assert_awaited_once()

    kwargs = mock_open_process.call_args[1]
    assert "stdout" in kwargs
    assert kwargs["stdout"] == subprocess.DEVNULL
    assert "stderr" in kwargs
    assert kwargs["stderr"] == subprocess.DEVNULL


async def test_run_process_with_kwargs(mock_open_process):
    await run_process(["echo", "hello world"], env={"test_kwarg": "test_kwarg"})
    mock_open_process.assert_awaited_once()

    kwargs = mock_open_process.call_args[1]
    assert "env" in kwargs
    assert kwargs["env"] == {"test_kwarg": "test_kwarg"}


async def test_run_process_hides_output(capsys):
    process = await run_process(["echo", "hello world"], stream_output=False)
    assert process.returncode == 0

    out, err = capsys.readouterr()
    assert out == ""
    assert err == ""


async def test_run_process_captures_stdout(capsys):
    process = await run_process(["echo", "hello world"], stream_output=True)
    assert process.returncode == 0

    out, err = capsys.readouterr()
    assert out.strip() == "hello world"
    assert err == ""


@pytest.mark.skipif(
    sys.platform == "win32", reason="stderr redirect does not work on Windows"
)
async def test_run_process_captures_stderr(capsys):
    process = await run_process(
        ["bash", "-c", ">&2 echo hello world"], stream_output=True
    )
    assert process.returncode == 0

    out, err = capsys.readouterr()
    assert out == ""
    assert err.strip() == "hello world"


async def test_run_process_allows_stdout_fd(tmp_path):
    with open(tmp_path / "output.txt", "wt") as fout:
        process = await run_process(["echo", "hello world"], stream_output=(fout, None))

    assert process.returncode == 0
    assert (tmp_path / "output.txt").read_text().strip() == "hello world"


@pytest.mark.skipif(
    sys.platform == "win32", reason="stderr redirect does not work on Windows"
)
async def test_run_process_allows_stderr_fd(tmp_path):
    with open(tmp_path / "output.txt", "wt") as fout:
        process = await run_process(
            ["bash", "-c", ">&2 echo hello world"], stream_output=(None, fout)
        )
    assert process.returncode == 0
    assert (tmp_path / "output.txt").read_text().strip() == "hello world"


async def test_run_process_with_task_status(mock_open_process):
    fake_status = mock.MagicMock(spec=anyio.abc.TaskStatus)
    # By raising an exception when started is called we can assert the process
    # is opened before this time
    fake_status.started.side_effect = RuntimeError("Started called!")

    with pytest.raises(RuntimeError, match="Started called!"):
        await run_process(["echo", "hello world"], task_status=fake_status)

    fake_status.started.assert_called_once()
    mock_open_process.assert_awaited_once()


@pytest.fixture
def mock_psutil_process(monkeypatch):
    return_value = mock.MagicMock(spec=psutil.Process)
    monkeypatch.setattr("psutil.Process", mock.MagicMock())
    psutil.Process.return_value = return_value
    yield psutil.Process


def test_stop_process_with_defaults(mock_psutil_process, tmp_path):
    pid_file = tmp_path / "test.pid"
    pid_file.write_text("123")

    stop_process(pid_file)
    mock_psutil_process.assert_called_once_with(123)
    mock_psutil_process.return_value.terminate.assert_called()
    mock_psutil_process.return_value.wait.assert_called_with(3)
    mock_psutil_process.return_value.kill.assert_not_called()

    # Make sure that deleted the PID file.
    assert os.path.exists(pid_file) is False


def test_stop_process_with_timeout_expired(mock_psutil_process, tmp_path):
    mock_psutil_process.return_value.wait.side_effect = psutil.TimeoutExpired(None)

    pid_file = tmp_path / "test.pid"
    pid_file.write_text("123")

    stop_process(pid_file)
    mock_psutil_process.assert_called_once_with(123)
    mock_psutil_process.return_value.terminate.assert_called()
    mock_psutil_process.return_value.wait.assert_called_with(3)
    mock_psutil_process.return_value.kill.assert_called()

    # Make sure that deleted the PID file.
    assert os.path.exists(pid_file) is False


def test_stop_process_with_invalid_pid_file(mock_psutil_process, tmp_path):
    pid_file = tmp_path / "test.pid"
    assert os.path.exists(pid_file) is False

    with pytest.raises(
        OSError, match=f"Could not read PID from file {str(pid_file)!r}:"
    ):
        stop_process(pid_file)

    mock_psutil_process.assert_not_called()


def test_stop_process_with_invalid_pid(mock_psutil_process, tmp_path):
    pid_file = tmp_path / "test.pid"
    pid_file.write_text("test")

    with pytest.raises(ValueError, match=f"Invalid PID file {str(pid_file)!r}:"):
        stop_process(pid_file)

    mock_psutil_process.assert_not_called()

    # Make sure you haven't deleted the PID file because it might not be linked with
    # the process.
    assert os.path.exists(pid_file) is True


def test_stop_process_with_zombie_process(mock_psutil_process, tmp_path):
    mock_psutil_process.side_effect = psutil.NoSuchProcess("process PID not found")

    pid_file = tmp_path / "test.pid"
    pid_file.write_text("123")

    with pytest.raises(ProcessLookupError, match="process PID not found"):
        stop_process(pid_file)

    mock_psutil_process.assert_called_once_with(123)

    # Make sure you deleted the PID file because it is from a process that no longer
    # exists.
    assert os.path.exists(pid_file) is False


def test_stop_process_with_insufficient_privileges(mock_psutil_process, tmp_path):
    mock_psutil_process.return_value.terminate.side_effect = psutil.AccessDenied(
        "insufficient privileges"
    )

    pid_file = tmp_path / "test.pid"
    pid_file.write_text("123")

    with pytest.raises(PermissionError, match="insufficient privileges"):
        stop_process(pid_file)

    mock_psutil_process.assert_called_once_with(123)
    mock_psutil_process.return_value.terminate.assert_called()

    # Make sure you haven't deleted the PID file because it's from a process you don't
    # have access to.
    assert os.path.exists(pid_file) is True


class TestKillOnInterrupt:
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    def test_sends_sigterm_then_sigkill(self, monkeypatch):
        print_fn = mock.Mock()
        os_kill = mock.Mock()
        signal_receiver = mock.Mock()
        monkeypatch.setattr("os.kill", os_kill)
        monkeypatch.setattr("signal.signal", signal_receiver)

        kill_on_interrupt(123, "My Process", print_fn)

        # This is a bit convoluted, but the point of the `signal_receiver` mock
        # is to try to avoid actually sending the SIGINT. Doing so causes
        # pytest to receive the signal and cancel the test run. Note that this
        # doesn't happen with `signal.raise_signal`, but that's unavalable in
        # python 3.7.
        assert signal_receiver.call_args_list[0][0][0] == signal.SIGINT
        signal_handler = signal_receiver.call_args_list[0][0][1]
        signal_receiver.reset_mock()

        # Call SIGINT handler expect a SIGTERM
        signal_handler()
        print_fn.assert_called_once_with("\nStopping My Process...")
        os_kill.assert_called_once_with(123, signal.SIGTERM)

        # Reset mocks and send second SIGINT and expect SIGKILL
        print_fn.reset_mock()
        os_kill.reset_mock()

        assert signal_receiver.call_args_list[0][0][0] == signal.SIGINT
        signal_handler = signal_receiver.call_args_list[0][0][1]
        signal_handler()

        print_fn.assert_called_once_with("\nKilling My Process...")
        os_kill.assert_called_once_with(123, signal.SIGKILL)

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="CTRL_BREAK_EVENT is only defined in Windows",
    )
    def test_sends_ctrl_break_win32(self, monkeypatch):
        print_fn = mock.Mock()
        os_kill = mock.Mock()
        signal_receiver = mock.Mock()
        monkeypatch.setattr("os.kill", os_kill)
        monkeypatch.setattr("signal.signal", signal_receiver)

        kill_on_interrupt(123, "My Process", print_fn)

        assert signal_receiver.call_args_list[0][0][0] == signal.SIGINT
        signal_handler = signal_receiver.call_args_list[0][0][1]
        signal_handler()

        print_fn.assert_called_once_with("\nStopping My Process...")
        os_kill.assert_called_once_with(123, signal.CTRL_BREAK_EVENT)
