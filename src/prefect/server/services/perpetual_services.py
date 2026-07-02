"""
Perpetual services are background services that run on a periodic schedule using docket.

This module provides the registry and scheduling logic for perpetual services,
using docket's Perpetual dependency for distributed, HA-aware task scheduling.
"""

from __future__ import annotations

import logging
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, AsyncGenerator, Callable, TypeVar

from docket import Docket, Perpetual
from docket.dependencies import Dependency, get_single_dependency_parameter_of_type
from docket.execution import TaskFunction

from prefect.logging import get_logger

if TYPE_CHECKING:
    from docket import Worker

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
        await _replace_perpetual_service(docket, config)

    total = len(all_services)
    enabled = len(enabled_services)
    disabled = total - enabled
    logger.info(
        f"Perpetual services: {enabled} enabled, {disabled} disabled, {total} total"
    )


async def _replace_perpetual_service(
    docket: Docket, config: PerpetualServiceConfig
) -> None:
    """Force-(re)schedule a perpetual service using `docket.replace`.

    Unlike `docket.add` (which is a no-op when a task is already known,
    including stuck in *running* state), `replace` unconditionally
    overwrites the existing schedule.  This recovers perpetual services
    that were mid-execution when Redis went down and whose runs-hash is
    left with `state=running` after reconnection.
    """
    key = config.function.__name__
    await docket.replace(config.function, datetime.now(timezone.utc), key)()


class PerpetualServiceRecovery(Dependency["PerpetualServiceRecovery"]):
    """Worker dependency that force-reschedules perpetual services on each
    worker loop start (including after Redis reconnection).

    When a perpetual task is mid-execution during a Redis disruption, its
    runs-hash is left with `state=running`.  `docket.add()` (used by
    the worker's built-in `_schedule_all_automatic_perpetual_tasks`)
    considers running tasks already known and skips them.  This dependency
    hooks into the worker lifecycle to call `docket.replace()` instead,
    which unconditionally reschedules — clearing the stale state.
    """

    single = True

    def __init__(self, services: list[PerpetualServiceConfig]) -> None:
        self._services = services

    async def __aenter__(self) -> PerpetualServiceRecovery:
        return self

    @classmethod
    def worker_lifecycle(
        cls, docket: Docket, worker: Worker
    ) -> AbstractAsyncContextManager[None] | None:
        for dep in (worker.dependencies or {}).values():
            if isinstance(dep, cls):
                return dep._recovery_context(docket)
        return None  # pragma: no cover

    @asynccontextmanager
    async def _recovery_context(self, docket: Docket) -> AsyncGenerator[None, None]:
        for config in self._services:
            perpetual = get_single_dependency_parameter_of_type(
                config.function, Perpetual
            )
            if perpetual is None:
                continue
            logger.debug(
                f"Force-rescheduling perpetual service: {config.function.__name__}"
            )
            await _replace_perpetual_service(docket, config)
        yield
