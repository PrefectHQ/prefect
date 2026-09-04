"""Tests for unified class-based and perpetual background service discovery."""

from __future__ import annotations

import subprocess
import sys
import textwrap

from prefect.server.events.services.actions import Actions
from prefect.server.events.services.event_logger import EventLogger
from prefect.server.events.services.event_persister import EventPersister
from prefect.server.events.services.triggers import ReactiveTriggers
from prefect.server.events.stream import Distributor
from prefect.server.logs.stream import LogDistributor
from prefect.server.services._inventory import (
    _CATALOGED_PERPETUAL_FUNCTIONS,
    _TRIGGERS_ENVIRONMENT_VARIABLE,
    _TRIGGERS_SHARED_COMPONENTS,
    _get_service_inventory,
    _has_enabled_background_services,
)
from prefect.server.services.base import RunInEphemeralServers, RunInWebservers, Service
from prefect.server.services.perpetual_services import get_perpetual_services
from prefect.server.services.task_run_recorder import TaskRunRecorder
from prefect.settings.context import temporary_settings

CLASS_SERVICE_NAMES: tuple[str, ...] = (
    "TaskRunRecorder",
    "EventLogger",
    "EventPersister",
    "ReactiveTriggers",
    "Actions",
    "Distributor",
    "LogDistributor",
)

PERPETUAL_GROUP_NAMES: tuple[str, ...] = (
    "Scheduler",
    "Late Runs",
    "Cancellation Cleanup",
    "Pause Expirations",
    "Repossessor",
    "Cleanup Reconciler",
    "Foreman",
    "DB Vacuum",
    "Proactive Triggers",
    "Telemetry",
)

CLASS_SERVICE_DISABLE_UPDATES: dict[str, bool] = {
    "PREFECT_SERVER_SERVICES_TASK_RUN_RECORDER_ENABLED": False,
    "PREFECT_SERVER_SERVICES_EVENT_LOGGER_ENABLED": False,
    "PREFECT_SERVER_SERVICES_EVENT_PERSISTER_ENABLED": False,
    "PREFECT_SERVER_SERVICES_TRIGGERS_ENABLED": False,
    "PREFECT_SERVER_EVENTS_STREAM_OUT_ENABLED": False,
    "PREFECT_SERVER_LOGS_STREAM_OUT_ENABLED": False,
}

PERPETUAL_SERVICE_DISABLE_UPDATES: dict[str, bool | None] = {
    "PREFECT_SERVER_SERVICES_SCHEDULER_ENABLED": False,
    "PREFECT_SERVER_SERVICES_LATE_RUNS_ENABLED": False,
    "PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_ENABLED": False,
    "PREFECT_SERVER_SERVICES_PAUSE_EXPIRATIONS_ENABLED": False,
    "PREFECT_SERVER_SERVICES_REPOSSESSOR_ENABLED": False,
    "PREFECT_SERVER_SERVICES_CLEANUP_RECONCILER_ENABLED": False,
    "PREFECT_SERVER_SERVICES_FOREMAN_ENABLED": False,
    "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED": None,
    "PREFECT_SERVER_ANALYTICS_ENABLED": False,
    "PREFECT_SERVER_SERVICES_TRIGGERS_ENABLED": False,
}


def _item(name: str, **kwargs: bool):
    return next(item for item in _get_service_inventory(**kwargs) if item.name == name)


def test_existing_class_services_remain_discoverable():
    names = [item.name for item in _get_service_inventory() if item.kind == "class"]
    assert names == list(CLASS_SERVICE_NAMES)
    assert {item.name for item in _get_service_inventory() if item.kind == "class"} == {
        cls.__name__
        for cls in (
            TaskRunRecorder,
            EventLogger,
            EventPersister,
            ReactiveTriggers,
            Actions,
            Distributor,
            LogDistributor,
        )
    }


def test_perpetual_groups_are_discoverable():
    names = [item.name for item in _get_service_inventory() if item.kind == "perpetual"]
    assert names == list(PERPETUAL_GROUP_NAMES)


def test_inventory_catalog_covers_all_registered_perpetual_functions():
    registered = {config.function.__name__ for config in get_perpetual_services()}
    assert registered == set(_CATALOGED_PERPETUAL_FUNCTIONS)


def test_inventory_order_is_deterministic():
    first = [item.name for item in _get_service_inventory()]
    second = [item.name for item in _get_service_inventory()]
    assert first == second
    assert first == [*CLASS_SERVICE_NAMES, *PERPETUAL_GROUP_NAMES]


def test_scheduler_uses_shared_control():
    item = _item("Scheduler")
    assert item.shared_control is True
    assert item.components == (
        "schedule_deployments",
        "schedule_recent_deployments",
    )
    assert item.environment_variable == "PREFECT_SERVER_SERVICES_SCHEDULER_ENABLED"

    with temporary_settings({"PREFECT_SERVER_SERVICES_SCHEDULER_ENABLED": True}):
        assert _item("Scheduler").enabled is True
    with temporary_settings({"PREFECT_SERVER_SERVICES_SCHEDULER_ENABLED": False}):
        disabled = _item("Scheduler")
        assert disabled.enabled is False
        assert disabled.components == (
            "schedule_deployments",
            "schedule_recent_deployments",
        )


def test_cancellation_cleanup_uses_shared_control():
    item = _item("Cancellation Cleanup")
    assert item.shared_control is True
    assert item.components == (
        "ensure_cancelling_timeout_checks",
        "monitor_cancelled_flow_runs",
        "monitor_subflow_runs",
    )
    assert (
        item.environment_variable
        == "PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_ENABLED"
    )

    with temporary_settings(
        {"PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_ENABLED": True}
    ):
        assert _item("Cancellation Cleanup").enabled is True
    with temporary_settings(
        {"PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_ENABLED": False}
    ):
        assert _item("Cancellation Cleanup").enabled is False


def test_triggers_actions_and_proactive_share_one_setting():
    items = [
        item
        for item in _get_service_inventory()
        if item.environment_variable == _TRIGGERS_ENVIRONMENT_VARIABLE
    ]
    names = {item.name for item in items}
    assert names == {"ReactiveTriggers", "Actions", "Proactive Triggers"}
    assert all(item.shared_control for item in items)
    assert all(item.components == _TRIGGERS_SHARED_COMPONENTS for item in items)

    with temporary_settings({"PREFECT_SERVER_SERVICES_TRIGGERS_ENABLED": True}):
        enabled = {
            item.name: item.enabled
            for item in _get_service_inventory()
            if item.environment_variable == _TRIGGERS_ENVIRONMENT_VARIABLE
        }
        assert enabled == {
            "ReactiveTriggers": True,
            "Actions": True,
            "Proactive Triggers": True,
        }

    with temporary_settings({"PREFECT_SERVER_SERVICES_TRIGGERS_ENABLED": False}):
        disabled = {
            item.name: item.enabled
            for item in _get_service_inventory()
            if item.environment_variable == _TRIGGERS_ENVIRONMENT_VARIABLE
        }
        assert disabled == {
            "ReactiveTriggers": False,
            "Actions": False,
            "Proactive Triggers": False,
        }


def test_db_vacuum_component_state_for_set_bool_and_none():
    with temporary_settings(
        {
            "PREFECT_SERVER_SERVICES_EVENT_PERSISTER_ENABLED": True,
            "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED": {"events", "flow_runs"},
        }
    ):
        item = _item("DB Vacuum")
        assert item.shared_control is True
        assert item.components == ("events", "flow_runs")
        assert dict(item.component_state) == {"events": True, "flow_runs": True}
        assert item.enabled is True

    with temporary_settings(
        {
            "PREFECT_SERVER_SERVICES_EVENT_PERSISTER_ENABLED": True,
            "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED": True,
        }
    ):
        item = _item("DB Vacuum")
        assert dict(item.component_state) == {"events": True, "flow_runs": True}

    with temporary_settings(
        {
            "PREFECT_SERVER_SERVICES_EVENT_PERSISTER_ENABLED": True,
            "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED": False,
        }
    ):
        item = _item("DB Vacuum")
        assert dict(item.component_state) == {"events": True, "flow_runs": False}
        assert item.enabled is True

    with temporary_settings(
        {
            "PREFECT_SERVER_SERVICES_EVENT_PERSISTER_ENABLED": True,
            "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED": None,
        }
    ):
        item = _item("DB Vacuum")
        assert dict(item.component_state) == {"events": False, "flow_runs": False}
        assert item.enabled is False


def test_event_vacuum_disabled_when_event_persister_disabled():
    with temporary_settings(
        {
            "PREFECT_SERVER_SERVICES_EVENT_PERSISTER_ENABLED": False,
            "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED": {"events", "flow_runs"},
        }
    ):
        item = _item("DB Vacuum")
        assert dict(item.component_state) == {"events": False, "flow_runs": True}
        assert item.enabled is True


def test_telemetry_follows_analytics_enablement():
    item = _item("Telemetry")
    assert item.environment_variable == "PREFECT_SERVER_ANALYTICS_ENABLED"
    with temporary_settings({"PREFECT_SERVER_ANALYTICS_ENABLED": True}):
        assert _item("Telemetry").enabled is True
    with temporary_settings({"PREFECT_SERVER_ANALYTICS_ENABLED": False}):
        assert _item("Telemetry").enabled is False


def test_distributor_reports_canonical_environment_variable():
    item = _item("Distributor")
    assert item.environment_variable == "PREFECT_SERVER_EVENTS_STREAM_OUT_ENABLED"
    assert Distributor.environment_variable_name() == (
        "PREFECT_SERVER_EVENTS_STREAM_OUT_ENABLED"
    )


def test_class_only_configuration_is_eligible():
    with temporary_settings(
        {
            **PERPETUAL_SERVICE_DISABLE_UPDATES,
            **CLASS_SERVICE_DISABLE_UPDATES,
            "PREFECT_SERVER_SERVICES_TASK_RUN_RECORDER_ENABLED": True,
        }
    ):
        assert Service.enabled_services() == [TaskRunRecorder]
        assert get_perpetual_services()
        assert not [
            config for config in get_perpetual_services() if config.enabled_getter()
        ]
        assert _has_enabled_background_services() is True


def test_perpetual_only_configuration_is_eligible():
    with temporary_settings(
        {
            **CLASS_SERVICE_DISABLE_UPDATES,
            **PERPETUAL_SERVICE_DISABLE_UPDATES,
            "PREFECT_SERVER_SERVICES_SCHEDULER_ENABLED": True,
        }
    ):
        assert Service.enabled_services() == []
        enabled_perpetual = [
            config.function.__name__
            for config in get_perpetual_services()
            if config.enabled_getter()
        ]
        assert set(enabled_perpetual) == {
            "schedule_deployments",
            "schedule_recent_deployments",
        }
        assert _has_enabled_background_services() is True


def test_empty_service_configuration_is_not_eligible():
    with temporary_settings(
        {**CLASS_SERVICE_DISABLE_UPDATES, **PERPETUAL_SERVICE_DISABLE_UPDATES}
    ):
        assert Service.enabled_services() == []
        assert not [
            config for config in get_perpetual_services() if config.enabled_getter()
        ]
        assert _has_enabled_background_services() is False


def test_normal_ephemeral_and_webserver_filtering():
    normal = _get_service_inventory()
    ephemeral = _get_service_inventory(ephemeral=True)
    webserver = _get_service_inventory(webserver_only=True)

    assert {item.name for item in normal if item.kind == "class"} == {
        svc.__name__ for svc in Service.all_services()
    }
    assert {item.name for item in ephemeral if item.kind == "class"} == {
        svc.__name__ for svc in RunInEphemeralServers.all_services()
    }
    assert {item.name for item in webserver if item.kind == "class"} == {
        svc.__name__ for svc in RunInWebservers.all_services()
    }

    normal_names = {item.name for item in normal}
    ephemeral_names = {item.name for item in ephemeral}
    webserver_names = {item.name for item in webserver}

    assert "Scheduler" in normal_names
    assert "Scheduler" not in ephemeral_names
    assert "Scheduler" not in webserver_names

    assert "Cancellation Cleanup" in normal_names
    assert "Cancellation Cleanup" not in ephemeral_names
    assert "Cancellation Cleanup" not in webserver_names

    assert "Telemetry" in normal_names
    assert "Telemetry" in ephemeral_names
    assert "Telemetry" in webserver_names

    assert "Proactive Triggers" in normal_names
    assert "Proactive Triggers" in ephemeral_names
    assert "Proactive Triggers" not in webserver_names

    vacuum = next(item for item in ephemeral if item.name == "DB Vacuum")
    assert vacuum.components == ("events",)
    assert "flow_runs" not in dict(vacuum.component_state)


def test_discovery_is_independent_of_unrelated_import_order():
    script = textwrap.dedent(
        """\
        from prefect.server.services._inventory import (
            _CATALOGED_PERPETUAL_FUNCTIONS,
            _get_service_inventory,
        )
        from prefect.server.services.perpetual_services import get_perpetual_services

        items = _get_service_inventory()
        names = [item.name for item in items]
        required = {
            "TaskRunRecorder",
            "EventLogger",
            "EventPersister",
            "ReactiveTriggers",
            "Actions",
            "Distributor",
            "LogDistributor",
            "Scheduler",
            "Late Runs",
            "Cancellation Cleanup",
            "Pause Expirations",
            "Repossessor",
            "Cleanup Reconciler",
            "Foreman",
            "DB Vacuum",
            "Proactive Triggers",
            "Telemetry",
        }
        missing = required - set(names)
        assert not missing, missing
        registered = {
            config.function.__name__ for config in get_perpetual_services()
        }
        assert registered == set(_CATALOGED_PERPETUAL_FUNCTIONS)
        print("ok")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


DOCUMENTATION_ISOLATION_UPDATES: dict[str, bool | str] = {
    "PREFECT_SERVER_SERVICES_SCHEDULER_ENABLED": True,
    "PREFECT_SERVER_SERVICES_LATE_RUNS_ENABLED": True,
    "PREFECT_SERVER_SERVICES_TASK_RUN_RECORDER_ENABLED": False,
    "PREFECT_SERVER_SERVICES_EVENT_LOGGER_ENABLED": False,
    "PREFECT_SERVER_SERVICES_EVENT_PERSISTER_ENABLED": False,
    "PREFECT_SERVER_SERVICES_TRIGGERS_ENABLED": False,
    "PREFECT_SERVER_EVENTS_STREAM_OUT_ENABLED": False,
    "PREFECT_SERVER_LOGS_STREAM_OUT_ENABLED": False,
    "PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_ENABLED": False,
    "PREFECT_SERVER_SERVICES_PAUSE_EXPIRATIONS_ENABLED": False,
    "PREFECT_SERVER_SERVICES_REPOSSESSOR_ENABLED": False,
    "PREFECT_SERVER_SERVICES_CLEANUP_RECONCILER_ENABLED": False,
    "PREFECT_SERVER_SERVICES_FOREMAN_ENABLED": False,
    # Use the set value `events`, not false: false still maps to events.
    "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED": "events",
    "PREFECT_SERVER_ANALYTICS_ENABLED": False,
}


def test_documentation_isolation_recipe_enables_only_scheduler_and_late_runs():
    """Scheduler + Late Runs isolation must not leave event vacuum running.

    Event vacuum also requires the Event Persister. With persister disabled and
    `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED=events`, both vacuum components
    stay off. `false` is the wrong disable value because it maps to events.
    """
    with temporary_settings(DOCUMENTATION_ISOLATION_UPDATES):
        enabled = [item.name for item in _get_service_inventory() if item.enabled]
        assert enabled == ["Scheduler", "Late Runs"]

        vacuum = _item("DB Vacuum")
        assert vacuum.enabled is False
        assert dict(vacuum.component_state) == {"events": False, "flow_runs": False}
