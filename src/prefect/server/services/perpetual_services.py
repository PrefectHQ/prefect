"""
Perpetual services are background services that run on a periodic schedule using docket.

This module provides the registry and scheduling logic for perpetual services,
using docket's Perpetual dependency for distributed, HA-aware task scheduling.
"""

from __future__ import annotations

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


# Registry of all perpetual service functions
_PERPETUAL_SERVICES: list[PerpetualServiceConfig] = []


def perpetual_service(
    enabled_getter: EnabledGetter,
    run_in_ephemeral: bool = False,
    run_in_webserver: bool = False,
) -> Callable[[F], F]:
    """
    Decorator to register a perpetual service function.

    Args:
        enabled_getter: A callable that returns whether the service is enabled.
        run_in_ephemeral: If True, this service runs in ephemeral server mode.
        run_in_webserver: If True, this service runs in webserver-only mode.

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
