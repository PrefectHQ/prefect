"""Tests for perpetual services registration and scheduling."""

from prefect.server.events.services.triggers import (
    evaluate_proactive_triggers_perpetual,
)
from prefect.server.services.cancellation_cleanup import (
    monitor_cancelled_flow_runs,
    monitor_subflow_runs,
)
from prefect.server.services.foreman import monitor_worker_health
from prefect.server.services.late_runs import monitor_late_runs
from prefect.server.services.pause_expirations import monitor_expired_pauses
from prefect.server.services.perpetual_services import (
    get_enabled_perpetual_services,
    get_perpetual_services,
)
from prefect.server.services.repossessor import monitor_expired_leases
from prefect.server.services.scheduler import (
    schedule_deployments,
    schedule_recent_deployments,
)
from prefect.server.services.telemetry import send_telemetry_heartbeat
from prefect.settings import (
    PREFECT_API_SERVICES_SCHEDULER_ENABLED,
    PREFECT_SERVER_ANALYTICS_ENABLED,
    temporary_settings,
)


def test_all_perpetual_services_registered():
    """All perpetual services should be registered."""
    services = get_perpetual_services()
    functions = {config.function for config in services}

    expected = {
        # Scheduler
        schedule_deployments,
        schedule_recent_deployments,
        # Late runs
        monitor_late_runs,
        # Foreman
        monitor_worker_health,
        # Pause expirations
        monitor_expired_pauses,
        # Cancellation cleanup
        monitor_cancelled_flow_runs,
        monitor_subflow_runs,
        # Repossessor
        monitor_expired_leases,
        # Telemetry
        send_telemetry_heartbeat,
        # Proactive triggers
        evaluate_proactive_triggers_perpetual,
    }

    assert functions == expected


def test_ephemeral_mode_perpetual_services():
    """Only services marked with run_in_ephemeral should be returned in ephemeral mode."""
    services = get_perpetual_services(ephemeral=True)
    functions = {config.function for config in services}

    # Only telemetry runs in ephemeral mode
    assert functions == {send_telemetry_heartbeat}


def test_webserver_mode_perpetual_services():
    """Only services marked with run_in_webserver should be returned in webserver mode."""
    services = get_perpetual_services(webserver_only=True)
    functions = {config.function for config in services}

    # Only telemetry runs in webserver mode
    assert functions == {send_telemetry_heartbeat}


def test_enabled_perpetual_services_respects_settings():
    """Enabled services should be filtered based on settings.

    Note: Services are disabled by default in tests (see tests/conftest.py).
    This test verifies that enabling/disabling a service works correctly.
    """
    # Enable scheduler and verify it appears
    with temporary_settings({PREFECT_API_SERVICES_SCHEDULER_ENABLED: True}):
        services_enabled = get_enabled_perpetual_services()
        functions_enabled = {config.function for config in services_enabled}
        assert schedule_deployments in functions_enabled
        assert schedule_recent_deployments in functions_enabled

    # Disable scheduler (back to test defaults) and verify it's filtered out
    with temporary_settings({PREFECT_API_SERVICES_SCHEDULER_ENABLED: False}):
        services_disabled = get_enabled_perpetual_services()
        functions_disabled = {config.function for config in services_disabled}
        assert schedule_deployments not in functions_disabled
        assert schedule_recent_deployments not in functions_disabled


def test_telemetry_enabled_with_analytics_setting():
    """Telemetry should respect the analytics_enabled setting."""
    with temporary_settings({PREFECT_SERVER_ANALYTICS_ENABLED: True}):
        services = get_enabled_perpetual_services()
        functions = {config.function for config in services}

        assert send_telemetry_heartbeat in functions


def test_telemetry_disabled_with_analytics_setting():
    """Telemetry should respect the analytics_enabled setting when disabled."""
    with temporary_settings({PREFECT_SERVER_ANALYTICS_ENABLED: False}):
        services = get_enabled_perpetual_services()
        functions = {config.function for config in services}

        assert send_telemetry_heartbeat not in functions
