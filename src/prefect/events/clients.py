import abc
import asyncio
from types import TracebackType
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Type

from websockets.client import WebSocketClientProtocol, connect
from websockets.exceptions import ConnectionClosed

from prefect.events import Event


class EventsClient(abc.ABC):
    """The abstract interface for all Prefect Events clients"""

    async def emit(self, event: Event) -> None:
        """Emit a single event"""
        if not hasattr(self, "_in_context"):
            raise TypeError(
                "Events may only be emitted while this client is being used as a "
                "context manager"
            )
        return await self._emit(event)

    @abc.abstractmethod
    async def _emit(self, event: Event) -> None:  # pragma: no cover
        ...

    async def __aenter__(self) -> "EventsClient":
        self._in_context = True
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[Exception]],
        exc_val: Optional[Exception],
        exc_tb: Optional[TracebackType],
    ) -> None:
        del self._in_context
        return None


class NullEventsClient(EventsClient):
    """A Prefect Events client implementation that does nothing"""

    async def _emit(self, event: Event) -> None:
        pass


class AssertingEventsClient(EventsClient):
    """A Prefect Events client that records all events sent to it for inspection during
    tests."""

    last: ClassVar["AssertingEventsClient | None"] = None
    all: ClassVar[List["AssertingEventsClient"]] = []

    args: Tuple
    kwargs: Dict[str, Any]
    events: List[Event]

    def __init__(self, *args, **kwargs):
        AssertingEventsClient.last = self
        AssertingEventsClient.all.append(self)
        self.args = args
        self.kwargs = kwargs

    @classmethod
    def reset(cls) -> None:
        """Reset all captured instances and their events.  For use this between tests"""
        cls.last = None
        cls.all = []

    async def _emit(self, event: Event) -> None:
        self.events.append(event)

    async def __aenter__(self) -> "AssertingEventsClient":
        await super().__aenter__()
        self.events = []
        return self


class PrefectCloudEventsClient(EventsClient):
    """A Prefect Events client that streams Events to a Prefect Cloud Workspace"""

    _websocket: Optional[WebSocketClientProtocol]
    _unconfirmed_events: List[Event]

    def __init__(
        self,
        api_url: str,
        api_key: str,
        reconnection_attempts: int = 10,
        checkpoint_every: int = 20,
    ):
        """
        Args:
            api_url: The base URL for a Prefect Cloud workspace
            api_key: The API of an actor with the manage_events scope
            reconnection_attempts: When the client is disconnected, how many times
                the client should attempt to reconnect
            checkpoint_every: How often the client should sync with the server to
                confirm receipt of all previously sent events
        """
        socket_url = api_url.replace("https://", "wss://").replace("http://", "ws://")
        self._connect = connect(
            socket_url + "/events/in",
            extra_headers={"Authorization": f"bearer {api_key}"},
        )
        self._websocket = None
        self._reconnection_attempts = reconnection_attempts
        self._unconfirmed_events = []
        self._checkpoint_every = checkpoint_every

    async def __aenter__(self) -> "PrefectCloudEventsClient":
        # Don't handle any errors in the initial connection, because these are most
        # likely a permission or configuration issue that should propagate
        await super().__aenter__()
        await self._reconnect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[Exception]],
        exc_val: Optional[Exception],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self._websocket = None
        await self._connect.__aexit__(exc_type, exc_val, exc_tb)
        return await super().__aexit__(exc_type, exc_val, exc_tb)

    async def _reconnect(self) -> None:
        if self._websocket:
            self._websocket = None
            await self._connect.__aexit__(None, None, None)

        self._websocket = await self._connect.__aenter__()

        # make sure we have actually connected
        pong = await self._websocket.ping()
        await pong

        events_to_resend = self._unconfirmed_events
        # Clear the unconfirmed events here, because they are going back through emit
        # and will be added again through the normal checkpointing process
        self._unconfirmed_events = []
        for event in events_to_resend:
            await self.emit(event)

    async def _checkpoint(self, event: Event) -> None:
        assert self._websocket

        self._unconfirmed_events.append(event)

        unconfirmed_count = len(self._unconfirmed_events)
        if unconfirmed_count < self._checkpoint_every:
            return

        pong = await self._websocket.ping()
        await pong

        # once the pong returns, we know for sure that we've sent all the messages
        # we had enqueued prior to that.  There could be more that came in after, so
        # don't clear the list, just the ones that we are sure of.
        self._unconfirmed_events = self._unconfirmed_events[unconfirmed_count:]

    async def _emit(self, event: Event) -> None:
        assert self._websocket

        for i in range(self._reconnection_attempts + 1):
            try:
                # after the first time through this loop, we're recovering from a
                # ConnectionClosed, so reconnect now, resending any unconfirmed
                # events before we send this one.
                if i > 0:
                    await self._reconnect()

                await self._websocket.send(event.json())
                await self._checkpoint(event)

                return
            except ConnectionClosed:
                if i == self._reconnection_attempts:
                    # this was our final chance, raise the most recent error
                    raise

                if i > 2:
                    # let the first two attempts happen quickly in case this is just
                    # a standard load balancer timeout, but after that, just take a
                    # beat to let things come back around.
                    await asyncio.sleep(1)
