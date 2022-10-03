import os
import signal
import subprocess
import sys
from unittest import mock

import psutil
import pytest

from prefect.utilities.processutils import (
    kill_on_interrupt,
    parse_command,
    run_process,
    start_process,
    stop_process,
)


def test_parse_command_returns_list():
    result = parse_command(["echo", "hello world"])
    assert isinstance(result, list)
    assert result == ["echo", "hello world"]


def test_parse_command_returns_str(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")

    result = parse_command(["echo", "hello world"])
    assert isinstance(result, str)
    assert result == "echo hello world"


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


@pytest.fixture
def mock_subprocess_popen(monkeypatch) -> mock.MagicMock:
    _mock = mock.Mock(spec=subprocess.Popen)
    _mock.pid = 123456  # Fake PID
    _mock.return_value = _mock

    monkeypatch.setattr("subprocess.Popen", _mock)

    return _mock


def test_start_process(monkeypatch, mock_subprocess_popen):
    start_process(["echo", "hello world"])
    mock_subprocess_popen.assert_called_once()

    kwargs = mock_subprocess_popen.call_args[1]
    assert "stdout" in kwargs
    assert kwargs["stdout"] == subprocess.DEVNULL
    assert "stderr" in kwargs
    assert kwargs["stderr"] == subprocess.DEVNULL


def test_start_process_with_creation_flags(monkeypatch, mock_subprocess_popen):
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("subprocess.DETACHED_PROCESS", 123, raising=False)

    start_process(["echo", "hello world"])
    mock_subprocess_popen.assert_called_once()

    kwargs = mock_subprocess_popen.call_args[1]
    assert "creationflags" in kwargs
    assert kwargs["creationflags"] == 123


def test_start_process_with_kwargs(mock_subprocess_popen):
    start_process(["echo", "hello world"], env={"test_kwarg": "test_kwarg"})
    mock_subprocess_popen.assert_called_once()

    kwargs = mock_subprocess_popen.call_args[1]
    assert "env" in kwargs
    assert kwargs["env"] == {"test_kwarg": "test_kwarg"}


def test_start_process_with_pid_file(tmp_path, mock_subprocess_popen):
    pid_file = tmp_path / "test.pid"
    assert os.path.exists(pid_file) is False

    process = start_process(["echo", "hello world"], pid_file=pid_file)
    mock_subprocess_popen.assert_called_once()
    assert process.pid == 123456
    assert os.path.exists(pid_file) is True

    with open(pid_file, "r") as f:
        process_pid = f.read()
    assert str(process.pid) == process_pid


def test_start_process_with_invalid_command(mock_subprocess_popen):
    mock_subprocess_popen.side_effect = mock.MagicMock(
        side_effect=OSError("No such file or directory: command")
    )

    with pytest.raises(OSError, match="No such file or directory: command"):
        start_process(["test_invalid_command"], pid_file="path/to/pid_file")

    mock_subprocess_popen.assert_called_once()


def test_start_process_with_invalid_pid_file(monkeypatch, mock_subprocess_popen):
    mock_open = mock.mock_open()
    mock_open.side_effect = mock.Mock(side_effect=OSError("monk_open"))
    monkeypatch.setattr("builtins.open", mock_open)

    with pytest.raises(OSError, match="Unable to write PID file: monk_open"):
        start_process(["echo", "hello world"], pid_file="path/to/pid_file")

    mock_subprocess_popen.assert_called_once()
    mock_subprocess_popen.terminate.assert_called_once()
    mock_subprocess_popen.wait.assert_called_once()


@pytest.fixture
def mock_psutil_process(monkeypatch) -> mock.MagicMock:
    _mock = mock.Mock(spec=psutil.Process)
    _mock.return_value = _mock

    monkeypatch.setattr("psutil.Process", _mock)

    return _mock


def test_stop_process(mock_psutil_process, tmp_path):
    pid_file = tmp_path / "test.pid"
    with open(pid_file, "w") as f:
        f.write("123")

    stop_process(pid_file)
    mock_psutil_process.assert_called_once_with(123)
    mock_psutil_process.terminate.assert_called()
    mock_psutil_process.wait.assert_called_with(3)
    mock_psutil_process.kill.assert_not_called()

    # Make sure that deleted the PID file.
    assert os.path.exists(pid_file) is False


def test_stop_process_with_timeout_expired(mock_psutil_process, tmp_path):
    mock_psutil_process.wait.side_effect = psutil.TimeoutExpired(None)

    pid_file = tmp_path / "test.pid"
    with open(pid_file, "w") as f:
        f.write("123")

    stop_process(pid_file)
    mock_psutil_process.assert_called_once_with(123)
    mock_psutil_process.terminate.assert_called()
    mock_psutil_process.wait.assert_called_with(3)
    mock_psutil_process.kill.assert_called()

    # Make sure that deleted the PID file.
    assert os.path.exists(pid_file) is False


def test_stop_process_with_zombie_process(mock_psutil_process, tmp_path):
    mock_psutil_process.side_effect = mock.MagicMock(
        side_effect=psutil.NoSuchProcess("process PID not found")
    )

    pid_file = tmp_path / "test.pid"
    with open(pid_file, "w") as f:
        f.write("123")

    with pytest.raises(ProcessLookupError, match="process PID not found"):
        stop_process(pid_file)

    mock_psutil_process.assert_called_once_with(123)

    # Make sure that deleted the PID file.
    assert os.path.exists(pid_file) is False


def test_stop_process_with_invalid_pid_file(mock_psutil_process, tmp_path):
    pid_file = tmp_path / "test.pid"
    assert os.path.exists(pid_file) is False

    with pytest.raises(OSError, match="Unable to read PID file:"):
        stop_process(pid_file)

    mock_psutil_process.assert_not_called()

    # Make sure that deleted the PID file.
    assert os.path.exists(pid_file) is False


def test_stop_process_with_invalid_pid(mock_psutil_process, tmp_path):
    pid_file = tmp_path / "test.pid"
    with open(pid_file, "w") as f:
        f.write("test")

    with pytest.raises(ValueError, match="Invalid PID file:"):
        stop_process(pid_file)

    mock_psutil_process.assert_not_called()

    # Make sure that deleted the PID file.
    assert os.path.exists(pid_file) is False


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
