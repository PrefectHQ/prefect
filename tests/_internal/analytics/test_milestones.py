"""
Tests for milestone tracking.
"""

import json
from pathlib import Path
from unittest.mock import patch


class TestMilestones:
    """Test milestone tracking."""

    def test_milestone_not_reached_initially(self, clean_telemetry_state: Path):
        """Milestones should not be reached initially."""
        from prefect._internal.analytics.milestones import has_reached_milestone

        assert has_reached_milestone("first_flow_defined") is False
        assert has_reached_milestone("first_flow_run") is False
        assert has_reached_milestone("first_deployment_created") is False
        assert has_reached_milestone("first_schedule_created") is False

    def test_mark_milestone(self, clean_telemetry_state: Path):
        """Should mark milestone as reached."""
        from prefect._internal.analytics.milestones import (
            has_reached_milestone,
            mark_milestone,
        )

        assert has_reached_milestone("first_flow_defined") is False

        mark_milestone("first_flow_defined")

        assert has_reached_milestone("first_flow_defined") is True

    def test_milestones_persist(self, clean_telemetry_state: Path):
        """Milestones should persist to disk."""
        from prefect._internal.analytics.milestones import mark_milestone

        mark_milestone("first_flow_defined")

        # Verify file exists
        milestones_file = clean_telemetry_state / "milestones.json"
        assert milestones_file.exists()

        # Verify contents
        milestones = json.loads(milestones_file.read_text())
        assert milestones["first_flow_defined"] is True

    def test_try_mark_milestone_returns_true_first_time(
        self, clean_telemetry_state: Path, telemetry_disabled
    ):
        """try_mark_milestone should return True the first time."""
        with patch(
            "prefect._internal.analytics.emit._is_interactive_terminal",
            return_value=True,
        ):
            from prefect._internal.analytics.milestones import try_mark_milestone

            result = try_mark_milestone("first_flow_defined")

            assert result is True

    def test_try_mark_milestone_returns_false_second_time(
        self, clean_telemetry_state: Path, telemetry_disabled
    ):
        """try_mark_milestone should return False if already marked."""
        with patch(
            "prefect._internal.analytics.emit._is_interactive_terminal",
            return_value=True,
        ):
            from prefect._internal.analytics.milestones import try_mark_milestone

            try_mark_milestone("first_flow_defined")
            result = try_mark_milestone("first_flow_defined")

            assert result is False

    def test_try_mark_milestone_emits_event(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """try_mark_milestone should emit an event."""
        with (
            patch(
                "prefect._internal.analytics.emit._is_interactive_terminal",
                return_value=True,
            ),
            patch("prefect._internal.analytics.emit.emit_sdk_event") as mock_emit,
        ):
            from prefect._internal.analytics.milestones import try_mark_milestone

            try_mark_milestone("first_flow_defined")

            mock_emit.assert_called_once_with("first_flow_defined")

    def test_multiple_milestones_independent(self, clean_telemetry_state: Path):
        """Different milestones should be tracked independently."""
        from prefect._internal.analytics.milestones import (
            has_reached_milestone,
            mark_milestone,
        )

        mark_milestone("first_flow_defined")

        assert has_reached_milestone("first_flow_defined") is True
        assert has_reached_milestone("first_flow_run") is False

    def test_try_mark_milestone_skipped_in_non_tty(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """try_mark_milestone should skip in non-interactive terminals."""
        with (
            patch(
                "prefect._internal.analytics.emit._is_interactive_terminal",
                return_value=False,
            ),
            patch("prefect._internal.analytics.emit.emit_sdk_event") as mock_emit,
        ):
            from prefect._internal.analytics.milestones import try_mark_milestone

            result = try_mark_milestone("first_flow_defined")

            # Should return False and not emit event in non-TTY
            assert result is False
            mock_emit.assert_not_called()


class TestExistingUserDetection:
    """Test existing user detection and milestone pre-marking."""

    def test_new_user_not_detected_as_existing(self, clean_telemetry_state: Path):
        """A fresh PREFECT_HOME should not be detected as an existing user."""
        from prefect._internal.analytics.milestones import _is_existing_user

        assert _is_existing_user() is False

    def test_existing_user_detected_by_profiles(self, clean_telemetry_state: Path):
        """User with profiles.toml should be detected as existing."""
        from prefect._internal.analytics.milestones import _is_existing_user

        # Create profiles.toml in PREFECT_HOME (parent of clean_telemetry_state)
        prefect_home = clean_telemetry_state.parent
        (prefect_home / "profiles.toml").touch()

        assert _is_existing_user() is True

    def test_existing_user_detected_by_database(self, clean_telemetry_state: Path):
        """User with .prefect.db should be detected as existing."""
        from prefect._internal.analytics.milestones import _is_existing_user

        prefect_home = clean_telemetry_state.parent
        (prefect_home / ".prefect.db").touch()

        assert _is_existing_user() is True

    def test_existing_user_detected_by_storage(self, clean_telemetry_state: Path):
        """User with storage directory should be detected as existing."""
        from prefect._internal.analytics.milestones import _is_existing_user

        prefect_home = clean_telemetry_state.parent
        (prefect_home / "storage").mkdir()

        assert _is_existing_user() is True

    def test_milestones_pre_marked_for_existing_user(self, clean_telemetry_state: Path):
        """All milestones should be pre-marked for existing users."""
        from prefect._internal.analytics.milestones import (
            ALL_MILESTONES,
            _mark_existing_user_milestones,
            has_reached_milestone,
        )

        # Create indicator of existing user
        prefect_home = clean_telemetry_state.parent
        (prefect_home / "profiles.toml").touch()

        # Pre-mark milestones
        result = _mark_existing_user_milestones()

        assert result is True
        for milestone in ALL_MILESTONES:
            assert has_reached_milestone(milestone) is True

    def test_milestones_not_pre_marked_for_new_user(self, clean_telemetry_state: Path):
        """Milestones should not be pre-marked for new users."""
        from prefect._internal.analytics.milestones import (
            _mark_existing_user_milestones,
            has_reached_milestone,
        )

        # No existing user indicators
        result = _mark_existing_user_milestones()

        assert result is False
        assert has_reached_milestone("first_flow_defined") is False

    def test_milestones_only_pre_marked_once(self, clean_telemetry_state: Path):
        """Pre-marking should only happen once (when telemetry dir doesn't exist)."""
        from prefect._internal.analytics.milestones import (
            _mark_existing_user_milestones,
        )

        # Create indicator of existing user
        prefect_home = clean_telemetry_state.parent
        (prefect_home / "profiles.toml").touch()

        # First call should pre-mark
        result1 = _mark_existing_user_milestones()
        assert result1 is True

        # Second call should skip (telemetry dir exists now)
        result2 = _mark_existing_user_milestones()
        assert result2 is False
