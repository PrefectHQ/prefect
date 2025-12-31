import logging
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from prefect.testing.cli import invoke_and_assert


class TestLogsSend:
    def test_help(self):
        invoke_and_assert(
            ["logs", "send", "--help"],
            expected_output_contains="Send log messages to Prefect",
            expected_code=0,
        )

    def test_send_from_file(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        log_file.write_text("Test log message")

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", str(log_file)],
                expected_code=0,
            )

            mock_create_logs.assert_called_once()
            logs = mock_create_logs.call_args.args[0]
            assert len(logs) == 1
            assert logs[0].message == "Test log message"
            assert logs[0].level == logging.INFO
            assert logs[0].name == "prefect.logs.send"

    def test_send_with_custom_level(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        log_file.write_text("Error message")

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", "--level", "error", str(log_file)],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert logs[0].level == logging.ERROR

    def test_send_with_custom_name(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        log_file.write_text("Test message")

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", "--name", "my.custom.logger", str(log_file)],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert logs[0].name == "my.custom.logger"

    def test_send_with_flow_run_id(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        log_file.write_text("Test message")
        flow_run_id = uuid4()

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", "--flow-run-id", str(flow_run_id), str(log_file)],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert logs[0].flow_run_id == flow_run_id

    def test_send_per_line_mode(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        log_file.write_text("Line 1\nLine 2\nLine 3\n")

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", "--per-line", str(log_file)],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert len(logs) == 3
            assert logs[0].message == "Line 1"
            assert logs[1].message == "Line 2"
            assert logs[2].message == "Line 3"

    def test_send_per_line_skips_empty_lines(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        log_file.write_text("Line 1\n\nLine 2\n  \nLine 3")

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", "--per-line", str(log_file)],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert len(logs) == 3

    def test_send_per_line_same_timestamp(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        log_file.write_text("Line 1\nLine 2\nLine 3")

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", "--per-line", str(log_file)],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            # All logs should have the same timestamp
            assert logs[0].timestamp == logs[1].timestamp == logs[2].timestamp

    def test_send_empty_file_does_nothing(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        log_file.write_text("")

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", str(log_file)],
                expected_code=0,
            )

            mock_create_logs.assert_not_called()

    def test_send_whitespace_only_does_nothing(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        log_file.write_text("   \n  \n   ")

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", str(log_file)],
                expected_code=0,
            )

            mock_create_logs.assert_not_called()

    def test_send_invalid_level_errors(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        log_file.write_text("Test message")

        invoke_and_assert(
            ["logs", "send", "--level", "invalid", str(log_file)],
            expected_output_contains="Invalid log level",
            expected_code=1,
        )

    def test_send_api_failure_with_silent(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        log_file.write_text("Test message")

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
            side_effect=Exception("API error"),
        ):
            invoke_and_assert(
                ["logs", "send", "--silent", str(log_file)],
                expected_output="",
                expected_code=0,
            )

    def test_level_options(self, tmp_path: Path):
        """Test all valid log level options."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Test message")

        level_mappings = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }

        for level_name, level_value in level_mappings.items():
            with patch(
                "prefect.client.orchestration.PrefectClient.create_logs",
                new_callable=AsyncMock,
            ) as mock_create_logs:
                invoke_and_assert(
                    ["logs", "send", "--level", level_name, str(log_file)],
                    expected_code=0,
                )

                logs = mock_create_logs.call_args.args[0]
                assert logs[0].level == level_value, f"Failed for level {level_name}"

    def test_level_case_insensitive(self, tmp_path: Path):
        """Test that log levels are case insensitive."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Test message")

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", "--level", "ERROR", str(log_file)],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert logs[0].level == logging.ERROR

    def test_send_with_custom_timestamp(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        log_file.write_text("Test message")

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", "--timestamp", "2024-01-15T10:30:00Z", str(log_file)],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert logs[0].timestamp.year == 2024
            assert logs[0].timestamp.month == 1
            assert logs[0].timestamp.day == 15
            assert logs[0].timestamp.hour == 10
            assert logs[0].timestamp.minute == 30

    def test_auto_detect_flow_run_id_from_env(self, tmp_path: Path, monkeypatch):
        """Test that flow_run_id is auto-detected from PREFECT__FLOW_RUN_ID env var."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Test message")
        flow_run_id = uuid4()

        monkeypatch.setenv("PREFECT__FLOW_RUN_ID", str(flow_run_id))

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", str(log_file)],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert logs[0].flow_run_id == flow_run_id

    def test_explicit_flow_run_id_overrides_env(self, tmp_path: Path, monkeypatch):
        """Test that explicit --flow-run-id overrides env var."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Test message")
        env_flow_run_id = uuid4()
        explicit_flow_run_id = uuid4()

        monkeypatch.setenv("PREFECT__FLOW_RUN_ID", str(env_flow_run_id))

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                [
                    "logs",
                    "send",
                    "--flow-run-id",
                    str(explicit_flow_run_id),
                    str(log_file),
                ],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert logs[0].flow_run_id == explicit_flow_run_id

    def test_invalid_flow_run_id_in_env_is_ignored(self, tmp_path: Path, monkeypatch):
        """Test that invalid PREFECT__FLOW_RUN_ID is silently ignored."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Test message")

        monkeypatch.setenv("PREFECT__FLOW_RUN_ID", "not-a-valid-uuid")

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", str(log_file)],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert logs[0].flow_run_id is None

    def test_default_timestamp_is_set(self, tmp_path: Path):
        """Test that timestamp defaults to current time when not provided."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Test message")

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", str(log_file)],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert logs[0].timestamp is not None

    def test_custom_timestamp_with_per_line(self, tmp_path: Path):
        """Test that custom timestamp is used for all lines in per-line mode."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Line 1\nLine 2\nLine 3")

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                [
                    "logs",
                    "send",
                    "--per-line",
                    "--timestamp",
                    "2024-06-01T12:00:00Z",
                    str(log_file),
                ],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert len(logs) == 3
            for log in logs:
                assert log.timestamp.year == 2024
                assert log.timestamp.month == 6
                assert log.timestamp.day == 1

    def test_short_flag_aliases(self, tmp_path: Path):
        """Test that short flag aliases work."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Test message")
        flow_run_id = uuid4()

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                [
                    "logs",
                    "send",
                    "-l",
                    "warning",
                    "-n",
                    "my.logger",
                    "-f",
                    str(flow_run_id),
                    "-t",
                    "2024-03-15T08:00:00Z",
                    str(log_file),
                ],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert logs[0].level == logging.WARNING
            assert logs[0].name == "my.logger"
            assert logs[0].flow_run_id == flow_run_id
            assert logs[0].timestamp.year == 2024
            assert logs[0].timestamp.month == 3

    def test_no_flow_run_id_when_not_set(self, tmp_path: Path, monkeypatch):
        """Test that flow_run_id is None when neither env nor flag is set."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Test message")

        # Ensure env var is not set
        monkeypatch.delenv("PREFECT__FLOW_RUN_ID", raising=False)

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", str(log_file)],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert logs[0].flow_run_id is None

    def test_per_line_with_only_empty_lines_does_nothing(self, tmp_path: Path):
        """Test that per-line mode with only empty lines doesn't send anything."""
        log_file = tmp_path / "test.log"
        log_file.write_text("\n\n  \n\t\n")

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", "--per-line", str(log_file)],
                expected_code=0,
            )

            mock_create_logs.assert_not_called()

    def test_send_with_message_flag(self):
        """Test sending a log with --message flag."""
        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", "--message", "Build failed"],
                expected_code=0,
            )

            mock_create_logs.assert_called_once()
            logs = mock_create_logs.call_args.args[0]
            assert len(logs) == 1
            assert logs[0].message == "Build failed"

    def test_send_with_message_short_flag(self):
        """Test sending a log with -m flag."""
        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", "-m", "Quick message", "-l", "error"],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert logs[0].message == "Quick message"
            assert logs[0].level == logging.ERROR

    def test_message_takes_precedence_over_file(self, tmp_path: Path):
        """Test that --message takes precedence over file argument."""
        log_file = tmp_path / "test.log"
        log_file.write_text("File content")

        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", "--message", "Message content", str(log_file)],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert logs[0].message == "Message content"

    def test_empty_message_does_nothing(self):
        """Test that empty --message doesn't send anything."""
        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", "--message", "   "],
                expected_code=0,
            )

            mock_create_logs.assert_not_called()

    def test_message_with_per_line(self):
        """Test --message with --per-line splits into multiple logs."""
        with patch(
            "prefect.client.orchestration.PrefectClient.create_logs",
            new_callable=AsyncMock,
        ) as mock_create_logs:
            invoke_and_assert(
                ["logs", "send", "--message", "Line 1\nLine 2\nLine 3", "--per-line"],
                expected_code=0,
            )

            logs = mock_create_logs.call_args.args[0]
            assert len(logs) == 3
            assert logs[0].message == "Line 1"
            assert logs[1].message == "Line 2"
            assert logs[2].message == "Line 3"
