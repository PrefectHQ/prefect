"""
Tests for telemetry notice display.
"""

from pathlib import Path
from unittest.mock import patch


class TestTelemetryNotice:
    """Test telemetry notice display."""

    def test_notice_shown_in_tty(self, clean_telemetry_state: Path, capsys):
        """Notice should be shown in TTY."""
        with patch("sys.stdout.isatty", return_value=True):
            from prefect.sdk_analytics._notice import maybe_show_telemetry_notice

            maybe_show_telemetry_notice()

            captured = capsys.readouterr()
            assert "Prefect collects anonymous usage data" in captured.err

    def test_notice_not_shown_in_non_tty(self, clean_telemetry_state: Path, capsys):
        """Notice should not be shown in non-TTY."""
        with patch("sys.stdout.isatty", return_value=False):
            from prefect.sdk_analytics._notice import maybe_show_telemetry_notice

            maybe_show_telemetry_notice()

            captured = capsys.readouterr()
            assert captured.err == ""

    def test_notice_shown_only_once(self, clean_telemetry_state: Path, capsys):
        """Notice should only be shown once."""
        with patch("sys.stdout.isatty", return_value=True):
            from prefect.sdk_analytics._notice import maybe_show_telemetry_notice

            maybe_show_telemetry_notice()
            capsys.readouterr()  # Clear first output

            maybe_show_telemetry_notice()  # Second call

            captured = capsys.readouterr()
            assert captured.err == ""

    def test_notice_marker_created(self, clean_telemetry_state: Path):
        """Notice marker file should be created."""
        with patch("sys.stdout.isatty", return_value=True):
            from prefect.sdk_analytics._notice import maybe_show_telemetry_notice

            maybe_show_telemetry_notice()

            marker_file = clean_telemetry_state / "notice_shown"
            assert marker_file.exists()

    def test_notice_contains_opt_out_info(self, clean_telemetry_state: Path, capsys):
        """Notice should contain opt-out information."""
        with patch("sys.stdout.isatty", return_value=True):
            from prefect.sdk_analytics._notice import maybe_show_telemetry_notice

            maybe_show_telemetry_notice()

            captured = capsys.readouterr()
            assert "PREFECT_SERVER_ANALYTICS_ENABLED=false" in captured.err
            assert "DO_NOT_TRACK=1" in captured.err

    def test_notice_contains_docs_link(self, clean_telemetry_state: Path, capsys):
        """Notice should contain link to documentation."""
        with patch("sys.stdout.isatty", return_value=True):
            from prefect.sdk_analytics._notice import maybe_show_telemetry_notice

            maybe_show_telemetry_notice()

            captured = capsys.readouterr()
            assert "https://docs.prefect.io/develop/telemetry" in captured.err
