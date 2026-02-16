"""
Manages the partial causal ordering of events for a particular consumer.  This module
maintains a buffer of events to be processed, aiming to process them in the order they
occurred causally.
"""

import abc
from datetime import timedelta
import importlib
from typing import (
    TYPE_CHECKING,
    AsyncContextManager,
    List,
    Protocol,
    Union,
    runtime_checkable,
)
from uuid import UUID
from prefect.logging import get_logger
from prefect.server.events.schemas.events import Event, ReceivedEvent
from prefect.settings import get_current_settings

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)

# How long we'll retain preceding events (to aid with ordering)
PRECEDING_EVENT_LOOKBACK = timedelta(minutes=15)

# How long we'll retain events we've processed (to prevent re-processing an event)
PROCESSED_EVENT_LOOKBACK = timedelta(minutes=30)

# How long we'll remember that we've seen an event
SEEN_EXPIRATION = max(PRECEDING_EVENT_LOOKBACK, PROCESSED_EVENT_LOOKBACK)

# How deep we'll allow the recursion to go when processing events
MAX_DEPTH_OF_PRECEDING_EVENT = 20


@runtime_checkable
class CausalOrderingModule(Protocol):
    CausalOrdering: type["CausalOrdering"]


class EventArrivedEarly(Exception):
    def __init__(self, event: ReceivedEvent):
        self.event = event


class MaxDepthExceeded(Exception):
    def __init__(self, event: ReceivedEvent):
        self.event = event


class event_handler(Protocol):
    async def __call__(
        self, event: ReceivedEvent, depth: int = 0
    ) -> None: ...  # pragma: no cover


class CausalOrdering(abc.ABC):
    def __init__(self, scope: str):
        self.scope = scope

    @abc.abstractmethod
    async def event_has_been_seen(self, event: Union[UUID, Event]) -> bool: ...

    @abc.abstractmethod
    async def record_event_as_seen(self, event: ReceivedEvent) -> None: ...

    @abc.abstractmethod
    async def record_follower(self, event: ReceivedEvent) -> None: ...

    @abc.abstractmethod
    async def forget_follower(self, follower: ReceivedEvent) -> None: ...

    @abc.abstractmethod
    async def get_followers(self, leader: ReceivedEvent) -> List[ReceivedEvent]: ...

    @abc.abstractmethod
    async def get_lost_followers(self) -> List[ReceivedEvent]: ...

    @abc.abstractmethod
    def preceding_event_confirmed(
        self, handler: event_handler, event: ReceivedEvent, depth: int = 0
    ) -> AsyncContextManager[None]: ...


def get_triggers_causal_ordering() -> CausalOrdering:
    import_path = get_current_settings().server.events.causal_ordering
    causal_ordering_module = importlib.import_module(import_path)

    if not isinstance(causal_ordering_module, CausalOrderingModule):
        raise ValueError(
            f"Module at {import_path} does not export a CausalOrdering class. Please check your server.events.causal_ordering setting."
        )

    return causal_ordering_module.CausalOrdering(scope="triggers")


def get_task_run_recorder_causal_ordering() -> CausalOrdering:
    import_path = get_current_settings().server.events.causal_ordering
    causal_ordering_module = importlib.import_module(import_path)

    if not isinstance(causal_ordering_module, CausalOrderingModule):
        raise ValueError(
            f"Module at {import_path} does not export a CausalOrdering class. Please check your server.events.causal_ordering setting."
        )

    return causal_ordering_module.CausalOrdering(scope="task-run-recorder")
