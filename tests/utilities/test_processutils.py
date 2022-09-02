import signal
import sys
from unittest import mock

import pytest

from prefect.utilities.processutils import kill_on_interrupt, run_process


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
