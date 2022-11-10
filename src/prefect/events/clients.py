import abc
from types import TracebackType
from typing import List, Optional, Type

from .schemas import Event


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
    ) -> "EventsClient":
        return self


class NullEventsClient(EventsClient):
    """An implementation of the Prefect Events client that does nothing"""

    async def emit(self, event: Event) -> None:
        pass


class AssertingEventsClient(EventsClient):
    """An implementation of the Prefect Events client that records all events sent
    to it for inspection during tests."""

    events: List[Event]

    def __init__(self):
        self.events = []

    async def emit(self, event: Event) -> None:
        self.events.append(event)

    async def __aenter__(self) -> "AssertingEventsClient":
        self.events = []
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[Exception]],
        exc_val: Optional[Exception],
        exc_tb: Optional[TracebackType],
    ) -> "AssertingEventsClient":
        self.events = []
        return self
