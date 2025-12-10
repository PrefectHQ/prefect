"""
Perpetual services are background services that run on a periodic schedule using docket.

This module provides the registry and scheduling logic for perpetual services,
replacing the LoopService pattern with docket's Perpetual dependency.

Key outcomes preserved from LoopService:
- Services can be enabled/disabled via settings (PREFECT_SERVER_SERVICES_<NAME>_ENABLED)
- Services respect RunInEphemeralServers/RunInWebservers markers
- Services are only scheduled when enabled (disabled services never run)
- Automatic Perpetual functions are scheduled at worker startup
- Non-automatic Perpetual functions are explicitly scheduled based on settings
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable, TypeVar

from docket import Docket, Perpetual
from docket.dependencies import get_single_dependency_parameter_of_type

from prefect.logging import get_logger

if TYPE_CHECKING:
    from prefect.settings.models.server.services import ServicesBaseSetting

logger: logging.Logger = get_logger(__name__)

# Type aliases for perpetual service functions and getters
PerpetualServiceFunction = Callable[..., Awaitable[Any]]
"""An async function that can be registered as a perpetual service."""

SettingsGetter = Callable[[], "ServicesBaseSetting"]
"""A callable that returns a service settings object with an `enabled` attribute."""

EnabledGetter = Callable[[], bool]
"""A callable that returns whether a service is enabled."""

F = TypeVar("F", bound=PerpetualServiceFunction)


@dataclass
class PerpetualServiceConfig:
    """Configuration for a perpetual service function."""

    function: PerpetualServiceFunction
    settings_getter: SettingsGetter | None
    enabled_getter: EnabledGetter | None = None
    run_in_ephemeral: bool = False
    run_in_webserver: bool = False


# Registry of all perpetual service functions
_PERPETUAL_SERVICES: list[PerpetualServiceConfig] = []


def perpetual_service(
    settings_getter: SettingsGetter | None = None,
    enabled_getter: EnabledGetter | None = None,
    run_in_ephemeral: bool = False,
    run_in_webserver: bool = False,
) -> Callable[[F], F]:
    """
    Decorator to register a perpetual service function.

    Args:
        settings_getter: A callable that returns the service's settings object.
            The settings object must have an `enabled` attribute.
            Either settings_getter or enabled_getter must be provided.
        enabled_getter: A callable that returns whether the service is enabled.
            Use this for services with non-standard enabled checks (e.g., telemetry).
        run_in_ephemeral: If True, this service runs in ephemeral server mode.
        run_in_webserver: If True, this service runs in webserver-only mode.

    Example:
        @perpetual_service(
            settings_getter=lambda: get_current_settings().server.services.scheduler,
        )
        async def schedule_deployments(...) -> None:
            ...

        # For services with custom enabled checks:
        @perpetual_service(
            enabled_getter=lambda: get_current_settings().server.analytics_enabled,
            run_in_ephemeral=True,
            run_in_webserver=True,
        )
        async def send_telemetry_heartbeat(...) -> None:
            ...
    """
    if settings_getter is None and enabled_getter is None:
        raise ValueError("Either settings_getter or enabled_getter must be provided")

    def decorator(func: F) -> F:
        _PERPETUAL_SERVICES.append(
            PerpetualServiceConfig(
                function=func,
                settings_getter=settings_getter,
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
        # Check if service should run in this mode
        if webserver_only:
            if not config.run_in_webserver:
                continue
        elif ephemeral:
            if not config.run_in_ephemeral:
                continue
        # Default mode: run all services (not filtered by markers)

        services.append(config)

    return services


def _is_service_enabled(config: PerpetualServiceConfig) -> bool:
    """Check if a perpetual service is enabled."""
    # If custom enabled_getter is provided, use it
    if config.enabled_getter is not None:
        return config.enabled_getter()

    # Otherwise use settings_getter
    if config.settings_getter is not None:
        return config.settings_getter().enabled

    # Should never happen due to decorator validation
    return False


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
        if _is_service_enabled(config):
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
    Register enabled perpetual service functions with docket and schedule non-automatic ones.

    This function:
    1. Registers only ENABLED perpetual functions with docket
    2. Schedules non-automatic perpetual functions

    Automatic perpetual functions (automatic=True) are scheduled by docket workers
    at startup once they are registered.

    Disabled services are not registered at all, so they never run.

    Args:
        docket: The docket instance to register functions with.
        ephemeral: If True, only register services for ephemeral mode.
        webserver_only: If True, only register services for webserver mode.
    """
    # Get all services for this mode (for counting)
    all_services = get_perpetual_services(ephemeral, webserver_only)

    # Get only enabled services - disabled services are NOT registered
    enabled_services = get_enabled_perpetual_services(ephemeral, webserver_only)

    # Register only enabled perpetual functions
    for config in enabled_services:
        docket.register(config.function)
        logger.debug(f"Registered perpetual service: {config.function.__name__}")

    # Schedule non-automatic perpetual functions
    for config in enabled_services:
        perpetual = get_single_dependency_parameter_of_type(config.function, Perpetual)
        if perpetual is None:
            logger.warning(
                f"Perpetual service {config.function.__name__} has no Perpetual "
                "dependency - skipping scheduling"
            )
            continue

        # Automatic perpetual functions are scheduled by docket workers at startup
        if perpetual.automatic:
            logger.debug(
                f"Perpetual service {config.function.__name__} is automatic - "
                "will be scheduled by worker"
            )
            continue

        # Schedule non-automatic perpetual functions
        logger.info(f"Scheduling perpetual service: {config.function.__name__}")
        await docket.add(config.function, key=config.function.__name__)()

    # Log summary
    total = len(all_services)
    enabled = len(enabled_services)
    disabled = total - enabled
    logger.info(
        f"Perpetual services: {enabled} enabled, {disabled} disabled, {total} total"
    )
