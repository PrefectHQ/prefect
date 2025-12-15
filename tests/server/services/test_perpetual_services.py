"""Tests for the perpetual services registry and scheduling."""

from prefect.server.services.perpetual_services import (
    _PERPETUAL_SERVICES,
    get_enabled_perpetual_services,
    get_perpetual_services,
)


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
    # Proactive triggers IS marked for ephemeral mode
    assert "evaluate_proactive_triggers_periodic" in service_names


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
