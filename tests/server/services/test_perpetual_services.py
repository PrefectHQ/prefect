"""Tests for the perpetual services registry and scheduling."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from docket import Docket, Perpetual
from docket.dependencies import get_single_dependency_parameter_of_type

from prefect.server.services.perpetual_services import (
    _PERPETUAL_SERVICES,
    PerpetualServiceConfig,
    PerpetualServiceRecovery,
    _replace_perpetual_service,
    get_enabled_perpetual_services,
    get_perpetual_services,
    register_and_schedule_perpetual_services,
)

pytestmark = pytest.mark.clear_db


def test_db_vacuum_service_registered():
    """Test that db vacuum perpetual service is registered."""
    service_names = [config.function.__name__ for config in _PERPETUAL_SERVICES]
    assert "schedule_vacuum_tasks" in service_names


def test_db_vacuum_disabled_by_default():
    """Test that flow_runs vacuum is disabled by default (not in the enabled set)."""
    config = next(
        c for c in _PERPETUAL_SERVICES if c.function.__name__ == "schedule_vacuum_tasks"
    )
    assert config.enabled_getter() is False


def test_event_vacuum_service_registered():
    """Test that event vacuum perpetual service is registered."""
    service_names = [config.function.__name__ for config in _PERPETUAL_SERVICES]
    assert "schedule_event_vacuum_tasks" in service_names


def test_event_vacuum_enabled_by_default(monkeypatch):
    """Test that event vacuum is enabled by default when event persister is also enabled."""
    from prefect.settings.context import get_current_settings

    settings = get_current_settings()
    # The test suite disables event_persister globally; restore the production
    # default so we can verify that event vacuum is enabled when both settings
    # are at their defaults.
    monkeypatch.setattr(settings.server.services.event_persister, "enabled", True)

    config = next(
        c
        for c in _PERPETUAL_SERVICES
        if c.function.__name__ == "schedule_event_vacuum_tasks"
    )
    assert config.enabled_getter() is True


def test_event_vacuum_disabled_when_not_in_enabled_set(monkeypatch):
    """Test that event vacuum is disabled when 'events' is not in the enabled set."""
    from prefect.settings.context import get_current_settings

    settings = get_current_settings()
    monkeypatch.setattr(settings.server.services.event_persister, "enabled", True)
    monkeypatch.setattr(settings.server.services.db_vacuum, "enabled", set())

    config = next(
        c
        for c in _PERPETUAL_SERVICES
        if c.function.__name__ == "schedule_event_vacuum_tasks"
    )
    assert config.enabled_getter() is False


def test_event_vacuum_disabled_when_event_persister_disabled(monkeypatch):
    """Test that event vacuum is disabled when event persister is disabled.

    Operators who opted out of event processing via
    PREFECT_SERVER_SERVICES_EVENT_PERSISTER_ENABLED=false should not see
    unexpected trimming on upgrade.
    """
    from prefect.settings.context import get_current_settings

    settings = get_current_settings()
    monkeypatch.setattr(settings.server.services.event_persister, "enabled", False)

    config = next(
        c
        for c in _PERPETUAL_SERVICES
        if c.function.__name__ == "schedule_event_vacuum_tasks"
    )
    assert config.enabled_getter() is False


def test_flow_runs_vacuum_enabled_when_in_enabled_set(monkeypatch):
    """Test that flow_runs vacuum is enabled when 'flow_runs' is in the enabled set."""
    from prefect.settings.context import get_current_settings

    settings = get_current_settings()
    monkeypatch.setattr(
        settings.server.services.db_vacuum, "enabled", {"events", "flow_runs"}
    )

    config = next(
        c for c in _PERPETUAL_SERVICES if c.function.__name__ == "schedule_vacuum_tasks"
    )
    assert config.enabled_getter() is True


def test_event_vacuum_runs_in_ephemeral_mode():
    """Test that event vacuum runs in ephemeral mode (replacing EventPersister.trim())."""
    config = next(
        c
        for c in _PERPETUAL_SERVICES
        if c.function.__name__ == "schedule_event_vacuum_tasks"
    )
    assert config.run_in_ephemeral is True


def test_cancellation_cleanup_services_registered():
    """Test that cancellation cleanup perpetual services are registered."""
    service_names = [config.function.__name__ for config in _PERPETUAL_SERVICES]
    assert "monitor_cancelled_flow_runs" in service_names
    assert "monitor_subflow_runs" in service_names


def test_pause_expirations_service_registered():
    """Test that pause expirations perpetual service is registered."""
    service_names = [config.function.__name__ for config in _PERPETUAL_SERVICES]
    assert "monitor_expired_pauses" in service_names


def test_late_runs_service_registered():
    """Test that late runs perpetual service is registered."""
    service_names = [config.function.__name__ for config in _PERPETUAL_SERVICES]
    assert "monitor_late_runs" in service_names


def test_repossessor_service_registered():
    """Test that repossessor perpetual service is registered."""
    service_names = [config.function.__name__ for config in _PERPETUAL_SERVICES]
    assert "monitor_expired_leases" in service_names


def test_cleanup_reconciler_service_registered():
    """Test that cleanup reconciler perpetual service is registered."""
    service_names = [config.function.__name__ for config in _PERPETUAL_SERVICES]
    assert "reconcile_cleanup_delivery" in service_names


def test_foreman_service_registered():
    """Test that foreman perpetual service is registered."""
    service_names = [config.function.__name__ for config in _PERPETUAL_SERVICES]
    assert "monitor_worker_health" in service_names


def test_telemetry_service_registered():
    """Test that telemetry perpetual service is registered."""
    service_names = [config.function.__name__ for config in _PERPETUAL_SERVICES]
    assert "send_telemetry_heartbeat" in service_names


def test_telemetry_runs_in_all_modes():
    """Test that telemetry is configured to run in ephemeral and webserver modes."""
    config = next(
        c
        for c in _PERPETUAL_SERVICES
        if c.function.__name__ == "send_telemetry_heartbeat"
    )
    assert config.run_in_ephemeral is True
    assert config.run_in_webserver is True


def test_scheduler_services_registered():
    """Test that scheduler perpetual services are registered."""
    service_names = [config.function.__name__ for config in _PERPETUAL_SERVICES]
    assert "schedule_deployments" in service_names
    assert "schedule_recent_deployments" in service_names


def test_proactive_triggers_service_registered():
    """Test that proactive triggers perpetual service is registered."""
    service_names = [config.function.__name__ for config in _PERPETUAL_SERVICES]
    assert "evaluate_proactive_triggers_periodic" in service_names


def test_get_perpetual_services_returns_all_in_default_mode():
    """Test that get_perpetual_services returns all services in default mode."""
    services = get_perpetual_services(ephemeral=False, webserver_only=False)
    service_names = [config.function.__name__ for config in services]
    assert "monitor_cancelled_flow_runs" in service_names
    assert "monitor_subflow_runs" in service_names


def test_get_perpetual_services_filters_ephemeral_mode():
    """Test that ephemeral mode filters services correctly."""
    services = get_perpetual_services(ephemeral=True, webserver_only=False)
    # Cancellation cleanup services are not marked for ephemeral mode
    service_names = [config.function.__name__ for config in services]
    assert "monitor_cancelled_flow_runs" not in service_names
    assert "monitor_subflow_runs" not in service_names
    # Proactive triggers and event vacuum ARE marked for ephemeral mode
    assert "evaluate_proactive_triggers_periodic" in service_names
    assert "schedule_event_vacuum_tasks" in service_names


def test_get_perpetual_services_filters_webserver_mode():
    """Test that webserver mode filters services correctly."""
    services = get_perpetual_services(ephemeral=False, webserver_only=True)
    # Cancellation cleanup services are not marked for webserver mode
    service_names = [config.function.__name__ for config in services]
    assert "monitor_cancelled_flow_runs" not in service_names
    assert "monitor_subflow_runs" not in service_names


def test_get_enabled_perpetual_services_respects_settings(monkeypatch):
    """Test that get_enabled_perpetual_services respects the enabled setting."""
    from prefect.settings.context import get_current_settings

    settings = get_current_settings()

    # Enable cancellation cleanup
    monkeypatch.setattr(settings.server.services.cancellation_cleanup, "enabled", True)

    services = get_enabled_perpetual_services(ephemeral=False, webserver_only=False)
    service_names = [config.function.__name__ for config in services]
    assert "monitor_cancelled_flow_runs" in service_names
    assert "monitor_subflow_runs" in service_names

    # Disable cancellation cleanup
    monkeypatch.setattr(settings.server.services.cancellation_cleanup, "enabled", False)

    services = get_enabled_perpetual_services(ephemeral=False, webserver_only=False)
    service_names = [config.function.__name__ for config in services]
    assert "monitor_cancelled_flow_runs" not in service_names
    assert "monitor_subflow_runs" not in service_names


def test_all_perpetual_services_use_automatic_true():
    """All perpetual services must use automatic=True so the docket worker
    reschedules them after a Redis disruption."""
    for config in _PERPETUAL_SERVICES:
        perpetual = get_single_dependency_parameter_of_type(config.function, Perpetual)
        assert perpetual is not None, (
            f"{config.function.__name__} has no Perpetual dependency"
        )
        assert perpetual.automatic is True, (
            f"{config.function.__name__} uses automatic=False; "
            "all perpetual services must use automatic=True for Redis recovery"
        )


class TestPerpetualServiceRecovery:
    """Tests for Redis disruption recovery via docket.replace()."""

    @staticmethod
    def _make_task_and_config() -> PerpetualServiceConfig:
        """Create a minimal perpetual task function and config for testing."""

        async def fake_service(
            perpetual: Perpetual = Perpetual(
                automatic=True, every=timedelta(seconds=10)
            ),
        ) -> None:
            pass

        return PerpetualServiceConfig(
            function=fake_service,
            enabled_getter=lambda: True,
        )

    async def test_replace_perpetual_service_calls_docket_replace(self) -> None:
        """_replace_perpetual_service must use docket.replace (not add)."""
        config = self._make_task_and_config()
        mock_scheduler = AsyncMock()
        mock_docket = AsyncMock(spec=Docket)
        mock_docket.replace.return_value = mock_scheduler

        await _replace_perpetual_service(mock_docket, config)

        mock_docket.replace.assert_called_once()
        call_args = mock_docket.replace.call_args
        assert call_args[0][0] is config.function
        assert call_args[0][2] == config.function.__name__
        mock_scheduler.assert_awaited_once()

    async def test_register_and_schedule_uses_replace(self) -> None:
        """register_and_schedule_perpetual_services must use replace, not add."""
        with patch(
            "prefect.server.services.perpetual_services._replace_perpetual_service",
            new_callable=AsyncMock,
        ) as mock_replace:
            mock_docket = AsyncMock(spec=Docket)
            await register_and_schedule_perpetual_services(mock_docket)

            # At least one enabled service should have been replace-scheduled
            assert mock_replace.await_count > 0

    async def test_recovery_dependency_reschedules_on_lifecycle_entry(self) -> None:
        """PerpetualServiceRecovery.worker_lifecycle must force-reschedule
        services when the worker loop starts (i.e. on reconnection)."""
        config = self._make_task_and_config()
        recovery = PerpetualServiceRecovery([config])

        mock_scheduler = AsyncMock()
        mock_docket = AsyncMock(spec=Docket)
        mock_docket.replace.return_value = mock_scheduler

        # Simulate the worker lifecycle entering
        async with recovery._recovery_context(mock_docket):
            pass

        mock_docket.replace.assert_called_once()
        call_args = mock_docket.replace.call_args
        assert call_args[0][0] is config.function
        assert call_args[0][2] == config.function.__name__
        mock_scheduler.assert_awaited_once()

    async def test_recovery_dependency_skips_services_without_perpetual(self) -> None:
        """Services without a Perpetual dependency are skipped gracefully."""

        async def no_perpetual_service() -> None:
            pass

        config = PerpetualServiceConfig(
            function=no_perpetual_service,
            enabled_getter=lambda: True,
        )
        recovery = PerpetualServiceRecovery([config])

        mock_docket = AsyncMock(spec=Docket)

        async with recovery._recovery_context(mock_docket):
            pass

        mock_docket.replace.assert_not_called()

    def test_recovery_dependency_has_worker_lifecycle(self) -> None:
        """PerpetualServiceRecovery must expose worker_lifecycle for docket."""
        assert hasattr(PerpetualServiceRecovery, "worker_lifecycle")

    async def test_worker_lifecycle_finds_instance_in_dependencies(self) -> None:
        """worker_lifecycle classmethod finds the instance via worker.dependencies."""
        config = self._make_task_and_config()
        recovery = PerpetualServiceRecovery([config])

        mock_worker = AsyncMock()
        mock_worker.dependencies = {"__worker_dep_0__": recovery}
        mock_docket = AsyncMock(spec=Docket)

        cm = PerpetualServiceRecovery.worker_lifecycle(mock_docket, mock_worker)
        assert cm is not None
