"""Unified discovery of class-based and Docket perpetual background services.

This module is an internal helper for the CLI and startup eligibility checks.
It does not change how services execute.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Literal

from prefect.server.services.base import RunInEphemeralServers, RunInWebservers, Service
from prefect.server.services.perpetual_services import (
    _PERPETUAL_SERVICE_MODULES,
    PerpetualServiceConfig,
    _ensure_perpetual_services_loaded,
    get_enabled_perpetual_services,
    get_perpetual_services,
)

_ServiceKind = Literal["class", "perpetual"]

_GROUP_IDENTITY_FIELDS: tuple[str, ...] = (
    "environment_variable",
    "description",
    "shared_control",
    "extra_components",
    "show_component_state",
)
_MODULE_ORDER = {name: index for index, name in enumerate(_PERPETUAL_SERVICE_MODULES)}


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


def _component_name(config: PerpetualServiceConfig) -> str:
    return config.component or config.function.__name__


def _group_key(config: PerpetualServiceConfig) -> str:
    return config.display_name or config.function.__name__


def _inventory_sort_key(config: PerpetualServiceConfig) -> tuple[int, int]:
    """Order by the perpetual module load list, then source order within a module.

    Registration append order depends on whichever module was imported first.
    Inventory rows must stay deterministic regardless of that import path.
    """
    module_index = _MODULE_ORDER.get(config.function.__module__, len(_MODULE_ORDER))
    try:
        line = inspect.getsourcelines(config.function)[1]
    except OSError:
        line = 0
    return (module_index, line)


def _validate_group_metadata(name: str, configs: list[PerpetualServiceConfig]) -> None:
    first = configs[0]
    for config in configs[1:]:
        for field in _GROUP_IDENTITY_FIELDS:
            left = getattr(first, field)
            right = getattr(config, field)
            if left != right:
                raise ValueError(
                    f"Inconsistent inventory metadata for perpetual group {name!r}: "
                    f"{field} differs between {first.function.__name__!r} "
                    f"({left!r}) and {config.function.__name__!r} ({right!r})"
                )


def _displayed_components(configs: list[PerpetualServiceConfig]) -> tuple[str, ...]:
    """Return extra class-service names plus registry-derived perpetual components."""
    derived = tuple(_component_name(config) for config in configs)
    extra = configs[0].extra_components if configs else ()
    return (*extra, *derived)


def _shared_component_overlays(
    configs: list[PerpetualServiceConfig],
) -> dict[str, tuple[bool, tuple[str, ...]]]:
    overlays: dict[str, tuple[bool, tuple[str, ...]]] = {}
    for _name, group_configs in _grouped_perpetual_configs(configs):
        first = group_configs[0]
        if not first.extra_components:
            continue
        displayed = _displayed_components(group_configs)
        for extra_name in first.extra_components:
            overlays[extra_name] = (first.shared_control, displayed)
    return overlays


def _class_inventory_items(
    ephemeral: bool,
    webserver_only: bool,
    overlays: dict[str, tuple[bool, tuple[str, ...]]],
) -> list[_ServiceInventoryItem]:
    items: list[_ServiceInventoryItem] = []
    for svc in _class_service_subset(ephemeral, webserver_only).all_services():
        name = svc.__name__
        overlay = overlays.get(name)
        items.append(
            _ServiceInventoryItem(
                name=name,
                kind="class",
                enabled=bool(svc.enabled()),
                environment_variable=svc.environment_variable_name(),
                description=_first_line(inspect.getdoc(svc)),
                components=overlay[1] if overlay else (),
                shared_control=overlay[0] if overlay else False,
                run_in_ephemeral=issubclass(svc, RunInEphemeralServers),
                run_in_webserver=issubclass(svc, RunInWebservers),
            )
        )
    return items


def _grouped_perpetual_configs(
    configs: list[PerpetualServiceConfig],
) -> list[tuple[str, list[PerpetualServiceConfig]]]:
    groups: dict[str, list[PerpetualServiceConfig]] = {}
    order: list[str] = []
    for config in sorted(configs, key=_inventory_sort_key):
        name = _group_key(config)
        if name not in groups:
            groups[name] = []
            order.append(name)
        groups[name].append(config)
    grouped: list[tuple[str, list[PerpetualServiceConfig]]] = []
    for name in order:
        group_configs = groups[name]
        _validate_group_metadata(name, group_configs)
        grouped.append((name, group_configs))
    return grouped


def _component_state(
    configs: list[PerpetualServiceConfig],
) -> tuple[tuple[str, bool], ...]:
    return tuple(
        (_component_name(config), bool(config.enabled_getter())) for config in configs
    )


def _perpetual_inventory_items(
    ephemeral: bool,
    webserver_only: bool,
) -> list[_ServiceInventoryItem]:
    configs = get_perpetual_services(ephemeral=ephemeral, webserver_only=webserver_only)
    items: list[_ServiceInventoryItem] = []

    for name, group_configs in _grouped_perpetual_configs(configs):
        first = group_configs[0]
        components = _displayed_components(group_configs)

        component_state = (
            _component_state(group_configs) if first.show_component_state else ()
        )
        enabled = any(config.enabled_getter() for config in group_configs)

        items.append(
            _ServiceInventoryItem(
                name=name,
                kind="perpetual",
                enabled=enabled,
                environment_variable=first.environment_variable or "",
                description=first.description or "",
                components=components,
                shared_control=first.shared_control,
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
    grouped by registration `display_name` and ordered by the perpetual module
    load list, then source order within each module, so operators do not see
    independently toggleable rows for functions that share one environment
    variable.
    """
    _ensure_perpetual_services_loaded()
    overlays = _shared_component_overlays(get_perpetual_services())
    return [
        *_class_inventory_items(ephemeral, webserver_only, overlays),
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
