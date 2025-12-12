from __future__ import annotations

import abc
import asyncio
import inspect
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from logging import Logger
from types import ModuleType
from typing import AsyncGenerator, NoReturn, Sequence

from typing_extensions import Self

from prefect.logging.loggers import get_logger
from prefect.settings.models.root import canonical_environment_prefix
from prefect.settings.models.server.services import ServicesBaseSetting

logger: Logger = get_logger(__name__)


def _known_service_modules() -> list[ModuleType]:
    """Get list of Prefect server modules containing Service subclasses"""
    from prefect.server.events import stream
    from prefect.server.events.services import (
        actions,
        event_logger,
        event_persister,
        triggers,
    )
    from prefect.server.logs import stream as logs_stream
    from prefect.server.services import (
        task_run_recorder,
    )

    return [
        # Orchestration services
        task_run_recorder,
        # Events services
        event_logger,
        event_persister,
        triggers,
        actions,
        stream,
        # Logs services
        logs_stream,
    ]


class Service(ABC):
    name: str
    logger: Logger

    @classmethod
    @abstractmethod
    def service_settings(cls) -> ServicesBaseSetting:
        """The Prefect setting that controls whether the service is enabled"""
        ...

    @classmethod
    def environment_variable_name(cls) -> str:
        return canonical_environment_prefix(cls.service_settings()) + "ENABLED"

    @classmethod
    def enabled(cls) -> bool:
        """Whether the service is enabled"""
        return cls.service_settings().enabled

    @classmethod
    def all_services(cls) -> Sequence[type[Self]]:
        """Get list of all service classes"""
        discovered: list[type[Self]] = []
        for module in _known_service_modules():
            for _, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, cls)
                    and not inspect.isabstract(obj)
                ):
                    discovered.append(obj)
        return discovered

    @classmethod
    def enabled_services(cls) -> list[type[Self]]:
        """Get list of enabled service classes"""
        return [svc for svc in cls.all_services() if svc.enabled()]

    @classmethod
    @asynccontextmanager
    async def running(cls) -> AsyncGenerator[None, None]:
        """A context manager that runs enabled services on entry and stops them on
        exit."""
        service_tasks: dict[Service, asyncio.Task[None]] = {}
        for service_class in cls.enabled_services():
            service = service_class()
            service_tasks[service] = asyncio.create_task(service.start())

        try:
            yield
        finally:
            await asyncio.gather(*[service.stop() for service in service_tasks])
            await asyncio.gather(*service_tasks.values(), return_exceptions=True)

    @classmethod
    async def run_services(cls) -> NoReturn:
        """Run enabled services until cancelled."""
        async with cls.running():
            heat_death_of_the_universe = asyncio.get_running_loop().create_future()
            try:
                await heat_death_of_the_universe
            except asyncio.CancelledError:
                logger.info("Received cancellation, stopping services...")

    @abstractmethod
    async def start(self) -> NoReturn:
        """Start running the service, which may run indefinitely"""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the service"""
        ...

    def __init__(self):
        self.name = self.__class__.__name__
        self.logger = get_logger(f"server.services.{self.name.lower()}")


class RunInEphemeralServers(Service, abc.ABC):
    """
    A marker class for services that should run even when running an ephemeral server
    """

    pass


class RunInWebservers(Service, abc.ABC):
    """
    A marker class for services that should run when running a webserver
    """

    pass
