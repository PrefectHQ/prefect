import abc
from types import TracebackType
from typing import Optional, Type

from prefect.events.schemas import Event


class EventsClient(abc.ABC):
    """The abstract interface for a Prefect Events client"""

    @abc.abstractmethod
    async def emit(self, event: Event) -> None:
        ...

    async def __aenter__(self) -> "EventsClient":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[Exception]],
        exc_val: Optional[Exception],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        return None


class NullEventsClient(EventsClient):
    """An implementation of the Prefect Events client that does nothing"""

    async def emit(self, event: Event) -> None:
        pass
