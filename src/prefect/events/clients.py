import abc
import asyncio
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    List,
    MutableMapping,
    Optional,
    Tuple,
    Type,
    cast,
)
from uuid import UUID

import httpx
import orjson
import pendulum
from cachetools import TTLCache
from typing_extensions import Self
from websockets import Subprotocol
from websockets.client import WebSocketClientProtocol, connect
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
)

from prefect.client.base import PrefectHttpxAsyncClient
from prefect.events import Event
from prefect.logging import get_logger
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    PREFECT_EXPERIMENTAL_EVENTS,
)

if TYPE_CHECKING:
    from prefect.events.filters import EventFilter

logger = get_logger(__name__)


def get_events_client(
    reconnection_attempts: int = 10,
    checkpoint_every: int = 20,
) -> "EventsClient":
    api_url = PREFECT_API_URL.value()
    if isinstance(api_url, str) and api_url.startswith(PREFECT_CLOUD_API_URL.value()):
        return PrefectCloudEventsClient(
            reconnection_attempts=reconnection_attempts,
            checkpoint_every=checkpoint_every,
        )
    elif PREFECT_EXPERIMENTAL_EVENTS:
        if PREFECT_API_URL:
            return PrefectEventsClient(
                reconnection_attempts=reconnection_attempts,
                checkpoint_every=checkpoint_every,
            )
        else:
            return PrefectEphemeralEventsClient()

    raise RuntimeError(
        "The current server and client configuration does not support "
        "events.  Enable experimental events support with the "
        "PREFECT_EXPERIMENTAL_EVENTS setting."
    )


def get_events_subscriber(
    filter: Optional["EventFilter"] = None,
    reconnection_attempts: int = 10,
) -> "PrefectEventSubscriber":
    api_url = PREFECT_API_URL.value()
    if isinstance(api_url, str) and api_url.startswith(PREFECT_CLOUD_API_URL.value()):
        return PrefectCloudEventSubscriber(
            filter=filter, reconnection_attempts=reconnection_attempts
        )
    elif PREFECT_EXPERIMENTAL_EVENTS:
        return PrefectEventSubscriber(
            filter=filter, reconnection_attempts=reconnection_attempts
        )

    raise RuntimeError(
        "The current server and client configuration does not support "
        "events.  Enable experimental events support with the "
        "PREFECT_EXPERIMENTAL_EVENTS setting."
    )


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

    async def __aenter__(self) -> Self:
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
        """Reset all captured instances and their events. For use between
        tests"""
        cls.last = None
        cls.all = []

    async def _emit(self, event: Event) -> None:
        self.events.append(event)

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.events = []
        return self


def _get_api_url_and_key(
    api_url: Optional[str], api_key: Optional[str]
) -> Tuple[str, str]:
    api_url = api_url or PREFECT_API_URL.value()
    api_key = api_key or PREFECT_API_KEY.value()

    if not api_url or not api_key:
        raise ValueError(
            "api_url and api_key must be provided or set in the Prefect configuration"
        )

    return api_url, api_key


class PrefectEphemeralEventsClient(EventsClient):
    """A Prefect Events client that sends events to an ephemeral Prefect server"""

    def __init__(self):
        if not PREFECT_EXPERIMENTAL_EVENTS:
            raise ValueError(
                "PrefectEphemeralEventsClient can only be used when "
                "PREFECT_EXPERIMENTAL_EVENTS is set to True"
            )
        if PREFECT_API_KEY.value():
            raise ValueError(
                "PrefectEphemeralEventsClient cannot be used when PREFECT_API_KEY is set."
                " Please use PrefectEventsClient or PrefectCloudEventsClient instead."
            )
        from prefect.server.api.server import create_app

        app = create_app()

        self._http_client = PrefectHttpxAsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://ephemeral-prefect/api",
            enable_csrf_support=False,
        )

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        await self._http_client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[Exception]],
        exc_val: Optional[Exception],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self._websocket = None
        await self._http_client.__aexit__(exc_type, exc_val, exc_tb)
        return await super().__aexit__(exc_type, exc_val, exc_tb)

    async def _emit(self, event: Event) -> None:
        await self._http_client.post(
            "/events",
            json=[event.dict(json_compatible=True)],
        )


class PrefectEventsClient(EventsClient):
    """A Prefect Events client that streams events to a Prefect server"""

    _websocket: Optional[WebSocketClientProtocol]
    _unconfirmed_events: List[Event]

    def __init__(
        self,
        api_url: Optional[str] = None,
        reconnection_attempts: int = 10,
        checkpoint_every: int = 20,
    ):
        """
        Args:
            api_url: The base URL for a Prefect server
            reconnection_attempts: When the client is disconnected, how many times
                the client should attempt to reconnect
            checkpoint_every: How often the client should sync with the server to
                confirm receipt of all previously sent events
        """
        api_url = api_url or PREFECT_API_URL.value()
        if not api_url:
            raise ValueError(
                "api_url must be provided or set in the Prefect configuration"
            )

        self._events_socket_url = (
            api_url.replace("https://", "wss://")
            .replace("http://", "ws://")
            .rstrip("/")
            + "/events/in"
        )
        self._connect = connect(self._events_socket_url)
        self._websocket = None
        self._reconnection_attempts = reconnection_attempts
        self._unconfirmed_events = []
        self._checkpoint_every = checkpoint_every

    async def __aenter__(self) -> Self:
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
        for i in range(self._reconnection_attempts + 1):
            try:
                # If we're here and the websocket is None, then we've had a failure in a
                # previous reconnection attempt.
                #
                # Otherwise, after the first time through this loop, we're recovering
                # from a ConnectionClosed, so reconnect now, resending any unconfirmed
                # events before we send this one.
                if not self._websocket or i > 0:
                    await self._reconnect()
                    assert self._websocket

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


class PrefectCloudEventsClient(PrefectEventsClient):
    """A Prefect Events client that streams events to a Prefect Cloud Workspace"""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
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
        api_url, api_key = _get_api_url_and_key(api_url, api_key)
        super().__init__(
            api_url=api_url,
            reconnection_attempts=reconnection_attempts,
            checkpoint_every=checkpoint_every,
        )

        self._connect = connect(
            self._events_socket_url,
            extra_headers={"Authorization": f"bearer {api_key}"},
        )


SEEN_EVENTS_SIZE = 500_000
SEEN_EVENTS_TTL = 120


class PrefectEventSubscriber:
    """
    Subscribes to a Prefect event stream, yielding events as they occur.

    Example:

        from prefect.events.clients import PrefectEventSubscriber
        from prefect.events.filters import EventFilter, EventNameFilter

        filter = EventFilter(event=EventNameFilter(prefix=["prefect.flow-run."]))

        async with PrefectEventSubscriber(filter=filter) as subscriber:
            async for event in subscriber:
                print(event.occurred, event.resource.id, event.event)

    """

    _websocket: Optional[WebSocketClientProtocol]
    _filter: "EventFilter"
    _seen_events: MutableMapping[UUID, bool]

    _api_key: Optional[str]

    def __init__(
        self,
        api_url: Optional[str] = None,
        filter: Optional["EventFilter"] = None,
        reconnection_attempts: int = 10,
    ):
        """
        Args:
            api_url: The base URL for a Prefect Cloud workspace
            api_key: The API of an actor with the manage_events scope
            reconnection_attempts: When the client is disconnected, how many times
                the client should attempt to reconnect
        """
        if not api_url:
            api_url = cast(str, PREFECT_API_URL.value())
            self._api_key = None

        from prefect.events.filters import EventFilter

        self._filter = filter or EventFilter()  # type: ignore[call-arg]
        self._seen_events = TTLCache(maxsize=SEEN_EVENTS_SIZE, ttl=SEEN_EVENTS_TTL)

        socket_url = (
            api_url.replace("https://", "wss://")
            .replace("http://", "ws://")
            .rstrip("/")
        ) + "/events/out"

        logger.debug("Connecting to %s", socket_url)

        self._connect = connect(
            socket_url,
            subprotocols=[Subprotocol("prefect")],
        )
        self._websocket = None
        self._reconnection_attempts = reconnection_attempts
        if self._reconnection_attempts < 0:
            raise ValueError("reconnection_attempts must be a non-negative integer")

    async def __aenter__(self) -> Self:
        # Don't handle any errors in the initial connection, because these are most
        # likely a permission or configuration issue that should propagate
        await self._reconnect()
        return self

    async def _reconnect(self) -> None:
        logger.debug("Reconnecting...")
        if self._websocket:
            self._websocket = None
            await self._connect.__aexit__(None, None, None)

        self._websocket = await self._connect.__aenter__()

        # make sure we have actually connected
        logger.debug("  pinging...")
        pong = await self._websocket.ping()
        await pong

        logger.debug("  authenticating...")
        await self._websocket.send(
            orjson.dumps({"type": "auth", "token": self._api_key}).decode()
        )

        try:
            message: Dict[str, Any] = orjson.loads(await self._websocket.recv())
            logger.debug("  auth result %s", message)
            assert message["type"] == "auth_success", message.get("reason", "")
        except AssertionError as e:
            raise Exception(
                "Unable to authenticate to the event stream. Please ensure the "
                "provided api_key you are using is valid for this environment. "
                f"Reason: {e.args[0]}"
            )
        except ConnectionClosedError as e:
            reason = getattr(e.rcvd, "reason", None)
            msg = "Unable to authenticate to the event stream. Please ensure the "
            msg += "provided api_key you are using is valid for this environment. "
            msg += f"Reason: {reason}" if reason else ""
            raise Exception(msg) from e

        from prefect.events.filters import EventOccurredFilter

        self._filter.occurred = EventOccurredFilter(
            since=pendulum.now("UTC").subtract(minutes=1),
            until=pendulum.now("UTC").add(years=1),
        )

        logger.debug("  filtering events since %s...", self._filter.occurred.since)
        filter_message = {
            "type": "filter",
            "filter": self._filter.dict(json_compatible=True),
        }
        await self._websocket.send(orjson.dumps(filter_message).decode())

    async def __aexit__(
        self,
        exc_type: Optional[Type[Exception]],
        exc_val: Optional[Exception],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self._websocket = None
        await self._connect.__aexit__(exc_type, exc_val, exc_tb)

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> Event:
        assert self._reconnection_attempts >= 0
        for i in range(self._reconnection_attempts + 1):  # pragma: no branch
            try:
                # If we're here and the websocket is None, then we've had a failure in a
                # previous reconnection attempt.
                #
                # Otherwise, after the first time through this loop, we're recovering
                # from a ConnectionClosed, so reconnect now.
                if not self._websocket or i > 0:
                    await self._reconnect()
                    assert self._websocket

                while True:
                    message = orjson.loads(await self._websocket.recv())
                    event: Event = Event.parse_obj(message["event"])

                    if event.id in self._seen_events:
                        continue
                    self._seen_events[event.id] = True

                    return event
            except ConnectionClosedOK:
                logger.debug('Connection closed with "OK" status')
                raise StopAsyncIteration
            except ConnectionClosed:
                logger.debug(
                    "Connection closed with %s/%s attempts",
                    i + 1,
                    self._reconnection_attempts,
                )
                if i == self._reconnection_attempts:
                    # this was our final chance, raise the most recent error
                    raise

                if i > 2:
                    # let the first two attempts happen quickly in case this is just
                    # a standard load balancer timeout, but after that, just take a
                    # beat to let things come back around.
                    await asyncio.sleep(1)
        raise StopAsyncIteration


class PrefectCloudEventSubscriber(PrefectEventSubscriber):
    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        filter: Optional["EventFilter"] = None,
        reconnection_attempts: int = 10,
    ):
        """
        Args:
            api_url: The base URL for a Prefect Cloud workspace
            api_key: The API of an actor with the manage_events scope
            reconnection_attempts: When the client is disconnected, how many times
                the client should attempt to reconnect
        """
        api_url, api_key = _get_api_url_and_key(api_url, api_key)

        super().__init__(
            api_url=api_url,
            filter=filter,
            reconnection_attempts=reconnection_attempts,
        )

        self._api_key = api_key


class PrefectCloudAccountEventSubscriber(PrefectCloudEventSubscriber):
    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        filter: Optional["EventFilter"] = None,
        reconnection_attempts: int = 10,
    ):
        """
        Args:
            api_url: The base URL for a Prefect Cloud workspace
            api_key: The API of an actor with the manage_events scope
            reconnection_attempts: When the client is disconnected, how many times
                the client should attempt to reconnect
        """
        api_url, api_key = _get_api_url_and_key(api_url, api_key)

        account_api_url, _, _ = api_url.partition("/workspaces/")

        super().__init__(
            api_url=account_api_url,
            filter=filter,
            reconnection_attempts=reconnection_attempts,
        )

        self._api_key = api_key
