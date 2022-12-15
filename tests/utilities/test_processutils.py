import signal
import subprocess
import sys
from unittest import mock

import pytest

import prefect.utilities.processutils
from prefect.utilities.processutils import kill_on_interrupt, open_process, run_process


class TestRunProcess:
    async def test_run_process_hides_output(self, capsys):
        process = await run_process(["echo", "hello world"], stream_output=False)
        assert process.returncode == 0
        out, err = capsys.readouterr()
        assert out == ""
        assert err == ""

    async def test_run_process_captures_stdout(self, capsys):
        process = await run_process(["echo", "hello world"], stream_output=True)
        assert process.returncode == 0
        out, err = capsys.readouterr()
        assert out.strip() == "hello world"
        assert err == ""

    @pytest.mark.skipif(
        sys.platform == "win32", reason="stderr redirect does not work on Windows"
    )
    async def test_run_process_captures_stderr(self, capsys):
        process = await run_process(
            ["bash", "-c", ">&2 echo hello world"], stream_output=True
        )
        assert process.returncode == 0
        out, err = capsys.readouterr()
        assert out == ""
        assert err.strip() == "hello world"

    async def test_run_process_allows_stdout_fd(self, tmp_path):
        with open(tmp_path / "output.txt", "wt") as fout:
            process = await run_process(
                ["echo", "hello world"], stream_output=(fout, None)
            )

        assert process.returncode == 0
        assert (tmp_path / "output.txt").read_text().strip() == "hello world"

    @pytest.mark.skipif(
        sys.platform == "win32", reason="stderr redirect does not work on Windows"
    )
    async def test_run_process_allows_stderr_fd(self, tmp_path):
        with open(tmp_path / "output.txt", "wt") as fout:
            process = await run_process(
                ["bash", "-c", ">&2 echo hello world"], stream_output=(None, fout)
            )
        assert process.returncode == 0
        assert (tmp_path / "output.txt").read_text().strip() == "hello world"


class TestOpenProcess:
    str_cmd = "ls -a"
    list_cmd = ["ls", "-a"]

    async def test_errors_if_cmd_is_not_list(self):
        with pytest.raises(TypeError):
            async with open_process(command=self.str_cmd):
                pass

    async def test_runs_if_cmd_is_list(self):
        async with open_process(self.list_cmd) as process:
            assert process

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="CTRL_C_HANDLER is only defined in Windows",
    )
    async def test_adds_ctrl_c_handler_to_win32_process_group(self, monkeypatch):
        """
        If the process is a Windows process group, we need to add a handler for
        CTRL_C_EVENT to the process group so we can kill the process group
        when the user presses CTRL+C.
        """
        mock_ctrl_c_handler = mock.Mock()
        monkeypatch.setattr(
            prefect.utilities.processutils, "_win32_ctrl_handler", mock_ctrl_c_handler
        )
        mock_set_console_ctrl_handler = mock.Mock()
        monkeypatch.setattr(
            prefect.utilities.processutils.windll.kernel32,
            "SetConsoleCtrlHandler",
            mock_set_console_ctrl_handler,
        )

        mock_process = mock.AsyncMock()
        mock_process.terminate = mock.MagicMock()
        mock_open_process = mock.AsyncMock(return_value=mock_process)
        monkeypatch.setattr(
            prefect.utilities.processutils, "_open_anyio_process", mock_open_process
        )

        await prefect.utilities.processutils.run_process(
            self.list_cmd, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
        mock_open_process.assert_called_once_with(
            " ".join(self.list_cmd),
            stdout=mock.ANY,
            stderr=mock.ANY,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        mock_set_console_ctrl_handler.assert_called_once_with(mock_ctrl_c_handler, 1)


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
