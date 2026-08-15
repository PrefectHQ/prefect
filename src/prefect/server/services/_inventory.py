"""Unified discovery of class-based and Docket perpetual background services.

This module is an internal helper for the CLI and startup eligibility checks.
It does not change how services execute.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Literal

from prefect.server.services.base import RunInEphemeralServers, RunInWebservers, Service
from prefect.server.services.perpetual_services import (
    PerpetualServiceConfig,
    _ensure_perpetual_services_loaded,
    get_enabled_perpetual_services,
    get_perpetual_services,
)

_ServiceKind = Literal["class", "perpetual"]

_TRIGGERS_ENVIRONMENT_VARIABLE = "PREFECT_SERVER_SERVICES_TRIGGERS_ENABLED"
_TRIGGERS_SHARED_COMPONENTS: tuple[str, ...] = (
    "ReactiveTriggers",
    "Actions",
    "evaluate_proactive_triggers_periodic",
)

_VACUUM_FUNCTION_TO_TYPE: dict[str, str] = {
    "schedule_event_vacuum_tasks": "events",
    "schedule_vacuum_tasks": "flow_runs",
}


@dataclass(frozen=True)
class _ServiceInventoryItem:
    """Operator-facing description of a background service or logical group."""

    name: str
    kind: _ServiceKind
    enabled: bool
    environment_variable: str
    description: str
    components: tuple[str, ...] = ()
    shared_control: bool = False
    component_state: tuple[tuple[str, bool], ...] = ()
    run_in_ephemeral: bool = False
    run_in_webserver: bool = False

    def to_json_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "enabled": self.enabled,
            "environment_variable": self.environment_variable,
            "description": self.description,
            "kind": self.kind,
            "shared_control": self.shared_control,
        }
        if self.components:
            payload["components"] = list(self.components)
        if self.component_state:
            payload["component_state"] = dict(self.component_state)
        return payload


@dataclass(frozen=True)
class _PerpetualGroup:
    name: str
    function_names: tuple[str, ...]
    environment_variable: str
    description: str
    shared_control: bool = False
    extra_components: tuple[str, ...] = ()
    vacuum_types: bool = False


# Deterministic operator-facing groups covering every registered perpetual
# function. Shared settings are represented once; do not invent per-component
# environment variables.
_PERPETUAL_GROUPS: tuple[_PerpetualGroup, ...] = (
    _PerpetualGroup(
        name="Scheduler",
        function_names=("schedule_deployments", "schedule_recent_deployments"),
        environment_variable="PREFECT_SERVER_SERVICES_SCHEDULER_ENABLED",
        description="Schedules flow runs from deployments with active schedules.",
        shared_control=True,
    ),
    _PerpetualGroup(
        name="Late Runs",
        function_names=("monitor_late_runs",),
        environment_variable="PREFECT_SERVER_SERVICES_LATE_RUNS_ENABLED",
        description="Marks flow runs as Late if they are not started on time.",
    ),
    _PerpetualGroup(
        name="Cancellation Cleanup",
        function_names=(
            "ensure_cancelling_timeout_checks",
            "monitor_cancelled_flow_runs",
            "monitor_subflow_runs",
        ),
        environment_variable="PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_ENABLED",
        description=(
            "Cancels subflow runs and child tasks, and enforces CANCELLING timeouts."
        ),
        shared_control=True,
    ),
    _PerpetualGroup(
        name="Pause Expirations",
        function_names=("monitor_expired_pauses",),
        environment_variable="PREFECT_SERVER_SERVICES_PAUSE_EXPIRATIONS_ENABLED",
        description="Fails paused flow runs that are not resumed before their timeout.",
    ),
    _PerpetualGroup(
        name="Repossessor",
        function_names=("monitor_expired_leases",),
        environment_variable="PREFECT_SERVER_SERVICES_REPOSSESSOR_ENABLED",
        description="Revokes expired concurrency leases.",
    ),
    _PerpetualGroup(
        name="Cleanup Reconciler",
        function_names=("reconcile_cleanup_delivery",),
        environment_variable="PREFECT_SERVER_SERVICES_CLEANUP_RECONCILER_ENABLED",
        description="Reconciles expired worker cleanup message leases.",
    ),
    _PerpetualGroup(
        name="Foreman",
        function_names=("monitor_worker_health",),
        environment_variable="PREFECT_SERVER_SERVICES_FOREMAN_ENABLED",
        description="Monitors workers and marks stale resources as offline or not ready.",
    ),
    _PerpetualGroup(
        name="DB Vacuum",
        function_names=("schedule_event_vacuum_tasks", "schedule_vacuum_tasks"),
        environment_variable="PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED",
        description=(
            "Cleans up old events and flow runs. Event vacuum also requires "
            "the Event Persister to be enabled."
        ),
        shared_control=True,
        vacuum_types=True,
    ),
    _PerpetualGroup(
        name="Proactive Triggers",
        function_names=("evaluate_proactive_triggers_periodic",),
        environment_variable=_TRIGGERS_ENVIRONMENT_VARIABLE,
        description="Evaluates proactive automation triggers on a periodic schedule.",
        shared_control=True,
        extra_components=_TRIGGERS_SHARED_COMPONENTS,
    ),
    _PerpetualGroup(
        name="Telemetry",
        function_names=("send_telemetry_heartbeat",),
        environment_variable="PREFECT_SERVER_ANALYTICS_ENABLED",
        description=(
            "Sends anonymous telemetry data to Prefect to help improve the product."
        ),
    ),
)

_CATALOGED_PERPETUAL_FUNCTIONS: frozenset[str] = frozenset(
    name for group in _PERPETUAL_GROUPS for name in group.function_names
)


def _first_line(doc: str | None) -> str:
    if not doc:
        return ""
    return doc.split("\n", 1)[0].strip()


def _class_service_subset(
    ephemeral: bool,
    webserver_only: bool,
) -> type[Service]:
    if webserver_only:
        return RunInWebservers
    if ephemeral:
        return RunInEphemeralServers
    return Service


def _class_inventory_items(
    ephemeral: bool,
    webserver_only: bool,
) -> list[_ServiceInventoryItem]:
    items: list[_ServiceInventoryItem] = []
    for svc in _class_service_subset(ephemeral, webserver_only).all_services():
        name = svc.__name__
        shared = name in {"ReactiveTriggers", "Actions"}
        items.append(
            _ServiceInventoryItem(
                name=name,
                kind="class",
                enabled=bool(svc.enabled()),
                environment_variable=svc.environment_variable_name(),
                description=_first_line(inspect.getdoc(svc)),
                components=_TRIGGERS_SHARED_COMPONENTS if shared else (),
                shared_control=shared,
                run_in_ephemeral=issubclass(svc, RunInEphemeralServers),
                run_in_webserver=issubclass(svc, RunInWebservers),
            )
        )
    return items


def _configs_by_name(
    configs: list[PerpetualServiceConfig],
) -> dict[str, PerpetualServiceConfig]:
    return {config.function.__name__: config for config in configs}


def _vacuum_component_state(
    configs: list[PerpetualServiceConfig],
) -> tuple[tuple[str, bool], ...]:
    state: list[tuple[str, bool]] = []
    for config in configs:
        vacuum_type = _VACUUM_FUNCTION_TO_TYPE.get(config.function.__name__)
        if vacuum_type is None:
            continue
        state.append((vacuum_type, bool(config.enabled_getter())))
    return tuple(state)


def _perpetual_inventory_items(
    ephemeral: bool,
    webserver_only: bool,
) -> list[_ServiceInventoryItem]:
    configs = get_perpetual_services(ephemeral=ephemeral, webserver_only=webserver_only)
    by_name = _configs_by_name(configs)
    items: list[_ServiceInventoryItem] = []

    for group in _PERPETUAL_GROUPS:
        group_configs = [
            by_name[name] for name in group.function_names if name in by_name
        ]
        if not group_configs:
            continue

        components: tuple[str, ...]
        if group.extra_components:
            components = group.extra_components
        elif group.vacuum_types:
            components = tuple(
                _VACUUM_FUNCTION_TO_TYPE[config.function.__name__]
                for config in group_configs
                if config.function.__name__ in _VACUUM_FUNCTION_TO_TYPE
            )
        else:
            components = tuple(config.function.__name__ for config in group_configs)

        component_state = (
            _vacuum_component_state(group_configs) if group.vacuum_types else ()
        )
        enabled = any(config.enabled_getter() for config in group_configs)

        items.append(
            _ServiceInventoryItem(
                name=group.name,
                kind="perpetual",
                enabled=enabled,
                environment_variable=group.environment_variable,
                description=group.description,
                components=components,
                shared_control=group.shared_control,
                component_state=component_state,
                run_in_ephemeral=any(
                    config.run_in_ephemeral for config in group_configs
                ),
                run_in_webserver=any(
                    config.run_in_webserver for config in group_configs
                ),
            )
        )

    return items


def _get_service_inventory(
    *,
    ephemeral: bool = False,
    webserver_only: bool = False,
) -> list[_ServiceInventoryItem]:
    """Return class-based and perpetual services in deterministic order.

    Class services keep their existing discovery order. Perpetual services are
    grouped by shared settings so operators do not see independently toggleable
    rows for functions that share one environment variable.
    """
    _ensure_perpetual_services_loaded()
    return [
        *_class_inventory_items(ephemeral, webserver_only),
        *_perpetual_inventory_items(ephemeral, webserver_only),
    ]


def _has_enabled_background_services(
    *,
    ephemeral: bool = False,
    webserver_only: bool = False,
) -> bool:
    """Return True when at least one class-based or perpetual service should run.

    Used by both foreground `prefect server services start` and the hidden
    background manager so they share one eligibility check.
    """
    _ensure_perpetual_services_loaded()
    service_type = _class_service_subset(ephemeral, webserver_only)
    if service_type.enabled_services():
        return True
    return bool(
        get_enabled_perpetual_services(
            ephemeral=ephemeral, webserver_only=webserver_only
        )
    )
