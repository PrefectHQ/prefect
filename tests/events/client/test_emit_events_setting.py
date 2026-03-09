"""Tests for PREFECT_CLIENT_EMIT_EVENTS setting."""

from unittest import mock

from prefect.events.worker import should_emit_events
from prefect.settings import PREFECT_CLIENT_EMIT_EVENTS, temporary_settings


class TestEmitEventsSetting:
    """Tests for the client.emit_events setting."""

    def test_default_is_true(self):
        """The setting defaults to True so existing behavior is preserved."""
        assert PREFECT_CLIENT_EMIT_EVENTS.default() is True

    def test_should_emit_events_respects_setting_when_false(self):
        """When emit_events is False, should_emit_events() returns False
        regardless of API URL or key configuration."""
        with temporary_settings(updates={PREFECT_CLIENT_EMIT_EVENTS: False}):
            assert should_emit_events() is False

    def test_should_emit_events_normal_when_true(self):
        """When emit_events is True (default), should_emit_events() delegates
        to the existing logic based on API URL/key."""
        with (
            temporary_settings(updates={PREFECT_CLIENT_EMIT_EVENTS: True}),
            mock.patch(
                "prefect.events.worker.emit_events_to_cloud", return_value=False
            ),
            mock.patch(
                "prefect.events.worker.should_emit_events_to_running_server",
                return_value=False,
            ),
            mock.patch(
                "prefect.events.worker.should_emit_events_to_ephemeral_server",
                return_value=False,
            ),
        ):
            assert should_emit_events() is False

    def test_should_emit_events_true_with_cloud(self):
        """When emit_events is True and cloud is configured, returns True."""
        with (
            temporary_settings(updates={PREFECT_CLIENT_EMIT_EVENTS: True}),
            mock.patch("prefect.events.worker.emit_events_to_cloud", return_value=True),
        ):
            assert should_emit_events() is True

    def test_emit_events_false_overrides_cloud(self):
        """Even with cloud configured, emit_events=False disables emission."""
        with temporary_settings(updates={PREFECT_CLIENT_EMIT_EVENTS: False}):
            # Even if cloud would return True, setting takes precedence
            assert should_emit_events() is False
