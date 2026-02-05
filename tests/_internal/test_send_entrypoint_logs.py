import logging
import subprocess
import sys
from unittest.mock import MagicMock, patch
from uuid import UUID

from prefect._internal.send_entrypoint_logs import _send, main


class TestSend:
    def test_creates_error_log_with_flow_run_id(self):
        mock_client = MagicMock()
        flow_run_id = UUID("12345678-1234-5678-1234-567812345678")

        with patch(
            "prefect._internal.send_entrypoint_logs.get_client",
            return_value=MagicMock(__enter__=MagicMock(return_value=mock_client)),
        ):
            _send("test message", flow_run_id)

        mock_client.create_logs.assert_called_once()
        logs = mock_client.create_logs.call_args[0][0]
        assert len(logs) == 1
        assert logs[0].message == "test message"
        assert logs[0].level == logging.ERROR
        assert logs[0].flow_run_id == flow_run_id
        assert logs[0].name == "prefect.entrypoint"

    def test_works_without_flow_run_id(self):
        mock_client = MagicMock()

        with patch(
            "prefect._internal.send_entrypoint_logs.get_client",
            return_value=MagicMock(__enter__=MagicMock(return_value=mock_client)),
        ):
            _send("test message", None)

        logs = mock_client.create_logs.call_args[0][0]
        assert logs[0].flow_run_id is None


class TestMain:
    def test_reads_from_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        log_file.write_text("file content")

        with (
            patch("sys.argv", ["send_entrypoint_logs", str(log_file)]),
            patch("prefect._internal.send_entrypoint_logs._send") as mock_send,
        ):
            main()

        assert mock_send.called

    def test_reads_from_stdin(self):
        mock_stdin = MagicMock()
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = "stdin content"

        with (
            patch("sys.argv", ["send_entrypoint_logs"]),
            patch("sys.stdin", mock_stdin),
            patch("prefect._internal.send_entrypoint_logs._send") as mock_send,
        ):
            main()

        assert mock_send.called

    def test_skips_empty_content(self, tmp_path):
        log_file = tmp_path / "empty.log"
        log_file.write_text("   \n  ")

        with (
            patch("sys.argv", ["send_entrypoint_logs", str(log_file)]),
            patch("prefect._internal.send_entrypoint_logs._send") as mock_send,
        ):
            main()

        mock_send.assert_not_called()

    def test_reads_flow_run_id_from_env(self, tmp_path, monkeypatch):
        log_file = tmp_path / "test.log"
        log_file.write_text("content")
        monkeypatch.setenv(
            "PREFECT__FLOW_RUN_ID", "12345678-1234-5678-1234-567812345678"
        )

        with (
            patch("sys.argv", ["send_entrypoint_logs", str(log_file)]),
            patch("prefect._internal.send_entrypoint_logs._send") as mock_send,
        ):
            main()

        assert mock_send.called

    def test_ignores_invalid_flow_run_id(self, tmp_path, monkeypatch):
        log_file = tmp_path / "test.log"
        log_file.write_text("content")
        monkeypatch.setenv("PREFECT__FLOW_RUN_ID", "not-a-uuid")

        with (
            patch("sys.argv", ["send_entrypoint_logs", str(log_file)]),
            patch("prefect._internal.send_entrypoint_logs._send") as mock_send,
        ):
            main()

        assert mock_send.called

    def test_silently_swallows_exceptions(self, tmp_path):
        log_file = tmp_path / "test.log"
        log_file.write_text("content")

        with (
            patch("sys.argv", ["send_entrypoint_logs", str(log_file)]),
            patch(
                "prefect._internal.send_entrypoint_logs._send",
                side_effect=Exception("connection failed"),
            ),
        ):
            main()  # should not raise


class TestModuleInvocation:
    def test_invokable_as_module(self):
        result = subprocess.run(
            [sys.executable, "-m", "prefect._internal.send_entrypoint_logs"],
            capture_output=True,
            text=True,
            input="",
        )
        assert result.returncode == 0
