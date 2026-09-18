"""
Perpetual services are background services that run on a periodic schedule using docket.

This module provides the registry and scheduling logic for perpetual services,
using docket's Perpetual dependency for distributed, HA-aware task scheduling.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import Callable, TypeVar

from docket import Docket, Perpetual
from docket.dependencies import get_single_dependency_parameter_of_type
from docket.execution import TaskFunction

from prefect.logging import get_logger

logger: logging.Logger = get_logger(__name__)

EnabledGetter = Callable[[], bool]
"""A callable that returns whether a service is enabled."""

F = TypeVar("F", bound=TaskFunction)


@dataclass
class PerpetualServiceConfig:
    """Configuration for a perpetual service function."""

    function: TaskFunction
    enabled_getter: EnabledGetter
    run_in_ephemeral: bool = False
    run_in_webserver: bool = False
    display_name: str | None = None
    environment_variable: str | None = None
    description: str | None = None
    component: str | None = None
    shared_control: bool = False
    extra_components: tuple[str, ...] = ()
    show_component_state: bool = False


# Registry of all perpetual service functions
_PERPETUAL_SERVICES: list[PerpetualServiceConfig] = []

# Modules that register perpetual services via `@perpetual_service`. Importing
# these explicitly keeps discovery independent of unrelated import order.
_PERPETUAL_SERVICE_MODULES: tuple[str, ...] = (
    "prefect.server.events.services.triggers",
    "prefect.server.services.cancellation_cleanup",
    "prefect.server.services.cleanup_reconciler",
    "prefect.server.services.db_vacuum",
    "prefect.server.services.foreman",
    "prefect.server.services.late_runs",
    "prefect.server.services.pause_expirations",
    "prefect.server.services.repossessor",
    "prefect.server.services.scheduler",
    "prefect.server.services.telemetry",
)


def _ensure_perpetual_services_loaded() -> None:
    """Import every module that registers a perpetual service.

    Registration happens at import time via `@perpetual_service`. Callers that
    discover or schedule perpetual work must not rely on accidental imports
    from tests, the CLI, or `prefect.server.services.__init__`.
    """
    for module_name in _PERPETUAL_SERVICE_MODULES:
        importlib.import_module(module_name)


def perpetual_service(
    enabled_getter: EnabledGetter,
    run_in_ephemeral: bool = False,
    run_in_webserver: bool = False,
    *,
    display_name: str | None = None,
    environment_variable: str | None = None,
    description: str | None = None,
    component: str | None = None,
    shared_control: bool = False,
    extra_components: tuple[str, ...] = (),
    show_component_state: bool = False,
) -> Callable[[F], F]:
    """
    Decorator to register a perpetual service function.

    Args:
        enabled_getter: A callable that returns whether the service is enabled.
        run_in_ephemeral: If True, this service runs in ephemeral server mode.
        run_in_webserver: If True, this service runs in webserver-only mode.
        display_name: Operator-facing inventory group name. Functions that share
            a display name are shown as one row, ordered by the perpetual module
            load list and source order within each module.
        environment_variable: Canonical setting name shown in the inventory.
        description: Operator-facing inventory description.
        component: Inventory component name. Defaults to the function name.
        shared_control: If True, this group shares one enablement setting.
        extra_components: Additional related component names, such as class-based
            services that share this group's setting. These are prepended to
            components derived from registered perpetual functions.
        show_component_state: If True, the inventory shows per-component
            enabled/disabled state.

    Example:
        @perpetual_service(
            enabled_getter=lambda: get_current_settings().server.services.scheduler.enabled,
        )
        async def schedule_deployments(...) -> None:
            ...
    """

    def decorator(func: F) -> F:
        _PERPETUAL_SERVICES.append(
            PerpetualServiceConfig(
                function=func,
                enabled_getter=enabled_getter,
                run_in_ephemeral=run_in_ephemeral,
                run_in_webserver=run_in_webserver,
                display_name=display_name,
                environment_variable=environment_variable,
                description=description,
                component=component,
                shared_control=shared_control,
                extra_components=tuple(extra_components),
                show_component_state=show_component_state,
            )
        )
        return func

    return decorator


def get_perpetual_services(
    ephemeral: bool = False,
    webserver_only: bool = False,
) -> list[PerpetualServiceConfig]:
    """
    Get perpetual services that should run in the current mode.

    Args:
        ephemeral: If True, only return services marked with run_in_ephemeral.
        webserver_only: If True, only return services marked with run_in_webserver.

    Returns:
        List of perpetual service configurations to run.
    """
    _ensure_perpetual_services_loaded()
    services = []
    for config in _PERPETUAL_SERVICES:
        if webserver_only:
            if not config.run_in_webserver:
                continue
        elif ephemeral:
            if not config.run_in_ephemeral:
                continue

        services.append(config)

    return services


def get_enabled_perpetual_services(
    ephemeral: bool = False,
    webserver_only: bool = False,
) -> list[PerpetualServiceConfig]:
    """
    Get perpetual services that are enabled and should run in the current mode.

    Args:
        ephemeral: If True, only return services marked with run_in_ephemeral.
        webserver_only: If True, only return services marked with run_in_webserver.

    Returns:
        List of enabled perpetual service configurations.
    """
    services = []
    for config in get_perpetual_services(ephemeral, webserver_only):
        if config.enabled_getter():
            services.append(config)
        else:
            logger.debug(
                f"Skipping disabled perpetual service: {config.function.__name__}"
            )

    return services


async def register_and_schedule_perpetual_services(
    docket: Docket,
    ephemeral: bool = False,
    webserver_only: bool = False,
) -> None:
    """
    Register enabled perpetual service functions with docket and schedule them.

    Disabled services are not registered at all, so they never run.

    Args:
        docket: The docket instance to register functions with.
        ephemeral: If True, only register services for ephemeral mode.
        webserver_only: If True, only register services for webserver mode.
    """
    all_services = get_perpetual_services(ephemeral, webserver_only)
    enabled_services = get_enabled_perpetual_services(ephemeral, webserver_only)

    for config in enabled_services:
        docket.register(config.function)
        logger.debug(f"Registered perpetual service: {config.function.__name__}")

    for config in enabled_services:
        perpetual = get_single_dependency_parameter_of_type(config.function, Perpetual)
        if perpetual is None:
            logger.warning(
                f"Perpetual service {config.function.__name__} has no Perpetual "
                "dependency - skipping scheduling"
            )
            continue

        logger.info(f"Scheduling perpetual service: {config.function.__name__}")
        await docket.add(config.function, key=config.function.__name__)()

    total = len(all_services)
    enabled = len(enabled_services)
    disabled = total - enabled
    logger.info(
        f"Perpetual services: {enabled} enabled, {disabled} disabled, {total} total"
    )
