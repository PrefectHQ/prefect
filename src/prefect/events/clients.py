import abc
import asyncio
import os
import ssl
from datetime import timedelta
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    Generator,
    List,
    MutableMapping,
    Optional,
    Tuple,
    Type,
    cast,
)
from urllib.parse import urlparse
from urllib.request import proxy_bypass
from uuid import UUID

import certifi
import orjson
from cachetools import TTLCache
from prometheus_client import Counter
from python_socks.async_.asyncio import Proxy
from typing_extensions import Self
from websockets import Subprotocol
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
)

import prefect.types._datetime
from prefect.events import Event
from prefect.logging import get_logger
from prefect.settings import (
    PREFECT_API_AUTH_STRING,
    PREFECT_API_KEY,
    PREFECT_API_SSL_CERT_FILE,
    PREFECT_API_TLS_INSECURE_SKIP_VERIFY,
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    PREFECT_DEBUG_MODE,
    PREFECT_SERVER_ALLOW_EPHEMERAL_MODE,
)

if TYPE_CHECKING:
    from prefect.events.filters import EventFilter

EVENTS_EMITTED = Counter(
    "prefect_events_emitted",
    "The number of events emitted by Prefect event clients",
    labelnames=["client"],
)
EVENTS_OBSERVED = Counter(
    "prefect_events_observed",
    "The number of events observed by Prefect event subscribers",
    labelnames=["client"],
)
EVENT_WEBSOCKET_CONNECTIONS = Counter(
    "prefect_event_websocket_connections",
    (
        "The number of times Prefect event clients have connected to an event stream, "
        "broken down by direction (in/out) and connection (initial/reconnect)"
    ),
    labelnames=["client", "direction", "connection"],
)
EVENT_WEBSOCKET_CHECKPOINTS = Counter(
    "prefect_event_websocket_checkpoints",
    "The number of checkpoints performed by Prefect event clients",
    labelnames=["client"],
)

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)


def http_to_ws(url: str) -> str:
    return url.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")


def events_in_socket_from_api_url(url: str) -> str:
    return http_to_ws(url) + "/events/in"


def events_out_socket_from_api_url(url: str) -> str:
    return http_to_ws(url) + "/events/out"


class WebsocketProxyConnect(connect):
    def __init__(self: Self, uri: str, **kwargs: Any):
        # super() is intentionally deferred to the _proxy_connect method
        # to allow for the socket to be established first

        self.uri = uri
        self._kwargs = kwargs

        u = urlparse(uri)
        host = u.hostname

        if not host:
            raise ValueError(f"Invalid URI {uri}, no hostname found")

        if u.scheme == "ws":
            port = u.port or 80
            proxy_url = os.environ.get("HTTP_PROXY")
        elif u.scheme == "wss":
            port = u.port or 443
            proxy_url = os.environ.get("HTTPS_PROXY")
            kwargs["server_hostname"] = host
        else:
            raise ValueError(
                "Unsupported scheme %s. Expected 'ws' or 'wss'. " % u.scheme
            )

        self._proxy = (
            Proxy.from_url(proxy_url) if proxy_url and not proxy_bypass(host) else None
        )
        self._host = host
        self._port = port

        if PREFECT_API_TLS_INSECURE_SKIP_VERIFY and u.scheme == "wss":
            # Create an unverified context for insecure connections
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self._kwargs.setdefault("ssl", ctx)
        elif u.scheme == "wss":
            cert_file = PREFECT_API_SSL_CERT_FILE.value()
            if not cert_file:
                cert_file = certifi.where()
            # Create a verified context with the certificate file
            ctx = ssl.create_default_context(cafile=cert_file)
            self._kwargs.setdefault("ssl", ctx)

    async def _proxy_connect(self: Self) -> ClientConnection:
        if self._proxy:
            sock = await self._proxy.connect(
                dest_host=self._host,
                dest_port=self._port,
            )
            self._kwargs["sock"] = sock

        super().__init__(self.uri, **self._kwargs)
        proto = await self.__await_impl__()
        return proto

    def __await__(self: Self) -> Generator[Any, None, ClientConnection]:
        return self._proxy_connect().__await__()


def websocket_connect(uri: str, **kwargs: Any) -> WebsocketProxyConnect:
    return WebsocketProxyConnect(uri, **kwargs)


def get_events_client(
    reconnection_attempts: int = 10,
    checkpoint_every: int = 700,
) -> "EventsClient":
    api_url = PREFECT_API_URL.value()
    if isinstance(api_url, str) and api_url.startswith(PREFECT_CLOUD_API_URL.value()):
        return PrefectCloudEventsClient(
            reconnection_attempts=reconnection_attempts,
            checkpoint_every=checkpoint_every,
        )
    elif api_url:
        return PrefectEventsClient(
            reconnection_attempts=reconnection_attempts,
            checkpoint_every=checkpoint_every,
        )
    elif PREFECT_SERVER_ALLOW_EPHEMERAL_MODE:
        from prefect.server.api.server import SubprocessASGIServer

        server = SubprocessASGIServer()
        server.start()
        return PrefectEventsClient(
            api_url=server.api_url,
            reconnection_attempts=reconnection_attempts,
            checkpoint_every=checkpoint_every,
        )
    else:
        raise ValueError(
            "No Prefect API URL provided. Please set PREFECT_API_URL to the address of a running Prefect server."
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
    elif api_url:
        return PrefectEventSubscriber(
            filter=filter, reconnection_attempts=reconnection_attempts
        )
    elif PREFECT_SERVER_ALLOW_EPHEMERAL_MODE:
        from prefect.server.api.server import SubprocessASGIServer

        server = SubprocessASGIServer()
        server.start()
        return PrefectEventSubscriber(
            api_url=server.api_url,
            filter=filter,
            reconnection_attempts=reconnection_attempts,
        )
    else:
        raise ValueError(
            "No Prefect API URL provided. Please set PREFECT_API_URL to the address of a running Prefect server."
        )


class EventsClient(abc.ABC):
    """The abstract interface for all Prefect Events clients"""

    @property
    def client_name(self) -> str:
        return self.__class__.__name__

    async def emit(self, event: Event) -> None:
        """Emit a single event"""
        if not hasattr(self, "_in_context"):
            raise TypeError(
                "Events may only be emitted while this client is being used as a "
                "context manager"
            )

        try:
            return await self._emit(event)
        finally:
            EVENTS_EMITTED.labels(self.client_name).inc()

    @abc.abstractmethod
    async def _emit(self, event: Event) -> None:  # pragma: no cover
        ...

    async def __aenter__(self) -> Self:
        self._in_context = True
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
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

    last: ClassVar["Optional[AssertingEventsClient]"] = None
    all: ClassVar[List["AssertingEventsClient"]] = []

    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    events: list[Event]

    def __init__(self, *args: Any, **kwargs: Any):
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

    def pop_events(self) -> List[Event]:
        events = self.events
        self.events = []
        return events

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


class PrefectEventsClient(EventsClient):
    """A Prefect Events client that streams events to a Prefect server"""

    _websocket: Optional[ClientConnection]
    _unconfirmed_events: List[Event]

    def __init__(
        self,
        api_url: Optional[str] = None,
        reconnection_attempts: int = 10,
        checkpoint_every: int = 700,
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

        self._events_socket_url = events_in_socket_from_api_url(api_url)
        self._connect = websocket_connect(self._events_socket_url)
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
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self._websocket = None
        await self._connect.__aexit__(exc_type, exc_val, exc_tb)
        return await super().__aexit__(exc_type, exc_val, exc_tb)

    def _log_debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        message = f"EventsClient(id={id(self)}): " + message
        logger.debug(message, *args, **kwargs)

    async def _reconnect(self) -> None:
        logger.debug("Reconnecting websocket connection.")

        if self._websocket:
            self._websocket = None
            await self._connect.__aexit__(None, None, None)
            logger.debug("Cleared existing websocket connection.")

        try:
            logger.debug("Opening websocket connection.")
            self._websocket = await self._connect.__aenter__()
            # make sure we have actually connected
            logger.debug("Pinging to ensure websocket connected.")
            pong = await self._websocket.ping()
            await pong
            logger.debug("Pong received. Websocket connected.")
        except Exception as e:
            # The client is frequently run in a background thread
            # so we log an additional warning to ensure
            # surfacing the error to the user.
            logger.warning(
                "Unable to connect to %r. "
                "Please check your network settings to ensure websocket connections "
                "to the API are allowed. Otherwise event data (including task run data) may be lost. "
                "Reason: %s. "
                "Set PREFECT_DEBUG_MODE=1 to see the full error.",
                self._events_socket_url,
                str(e),
                exc_info=PREFECT_DEBUG_MODE.value(),
            )
            raise

        events_to_resend = self._unconfirmed_events
        logger.debug("Resending %s unconfirmed events.", len(events_to_resend))
        # Clear the unconfirmed events here, because they are going back through emit
        # and will be added again through the normal checkpointing process
        self._unconfirmed_events = []
        for event in events_to_resend:
            await self.emit(event)
        logger.debug("Finished resending unconfirmed events.")

    async def _checkpoint(self) -> None:
        assert self._websocket

        unconfirmed_count = len(self._unconfirmed_events)

        if unconfirmed_count < self._checkpoint_every:
            return

        logger.debug("Pinging to checkpoint unconfirmed events.")
        pong = await self._websocket.ping()
        await pong
        self._log_debug("Pong received. Events checkpointed.")

        # once the pong returns, we know for sure that we've sent all the messages
        # we had enqueued prior to that.  There could be more that came in after, so
        # don't clear the list, just the ones that we are sure of.
        self._unconfirmed_events = self._unconfirmed_events[unconfirmed_count:]

        EVENT_WEBSOCKET_CHECKPOINTS.labels(self.client_name).inc()

    async def _emit(self, event: Event) -> None:
        self._log_debug("Emitting event id=%s.", event.id)

        self._unconfirmed_events.append(event)

        logger.debug(
            "Added event id=%s to unconfirmed events list. "
            "There are now %s unconfirmed events.",
            event.id,
            len(self._unconfirmed_events),
        )

        for i in range(self._reconnection_attempts + 1):
            self._log_debug("Emit reconnection attempt %s.", i)
            try:
                # If we're here and the websocket is None, then we've had a failure in a
                # previous reconnection attempt.
                #
                # Otherwise, after the first time through this loop, we're recovering
                # from a ConnectionClosed, so reconnect now, resending any unconfirmed
                # events before we send this one.
                if not self._websocket or i > 0:
                    self._log_debug("Attempting websocket reconnection.")
                    await self._reconnect()
                    assert self._websocket

                self._log_debug("Sending event id=%s.", event.id)
                await self._websocket.send(event.model_dump_json())
                self._log_debug("Checkpointing event id=%s.", event.id)
                await self._checkpoint()

                return
            except ConnectionClosed:
                self._log_debug("Got ConnectionClosed error.")
                if i == self._reconnection_attempts:
                    # this was our final chance, raise the most recent error
                    raise

                if i > 2:
                    # let the first two attempts happen quickly in case this is just
                    # a standard load balancer timeout, but after that, just take a
                    # beat to let things come back around.
                    logger.debug(
                        "Sleeping for 1 second before next reconnection attempt."
                    )
                    await asyncio.sleep(1)


class AssertingPassthroughEventsClient(PrefectEventsClient):
    """A Prefect Events client that BOTH records all events sent to it for inspection
    during tests AND sends them to a Prefect server."""

    last: ClassVar["Optional[AssertingPassthroughEventsClient]"] = None
    all: ClassVar[list["AssertingPassthroughEventsClient"]] = []

    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    events: list[Event]

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        AssertingPassthroughEventsClient.last = self
        AssertingPassthroughEventsClient.all.append(self)
        self.args = args
        self.kwargs = kwargs

    @classmethod
    def reset(cls) -> None:
        cls.last = None
        cls.all = []

    def pop_events(self) -> list[Event]:
        events = self.events
        self.events = []
        return events

    async def _emit(self, event: Event) -> None:
        # actually send the event to the server
        await super()._emit(event)

        # record the event for inspection
        self.events.append(event)

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.events = []
        return self


class PrefectCloudEventsClient(PrefectEventsClient):
    """A Prefect Events client that streams events to a Prefect Cloud Workspace"""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        reconnection_attempts: int = 10,
        checkpoint_every: int = 700,
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
        self._connect = websocket_connect(
            self._events_socket_url,
            additional_headers={"Authorization": f"bearer {api_key}"},
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

    _websocket: Optional[ClientConnection]
    _filter: "EventFilter"
    _seen_events: MutableMapping[UUID, bool]

    _api_key: Optional[str]
    _auth_token: Optional[str]

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
        self._api_key = None
        self._auth_token = PREFECT_API_AUTH_STRING.value()

        if not api_url:
            api_url = cast(str, PREFECT_API_URL.value())

        from prefect.events.filters import EventFilter

        self._filter = filter or EventFilter()  # type: ignore[call-arg]
        self._seen_events = TTLCache(maxsize=SEEN_EVENTS_SIZE, ttl=SEEN_EVENTS_TTL)

        socket_url = events_out_socket_from_api_url(api_url)

        logger.debug("Connecting to %s", socket_url)

        self._connect = websocket_connect(
            socket_url,
            subprotocols=[Subprotocol("prefect")],
        )
        self._websocket = None
        self._reconnection_attempts = reconnection_attempts
        if self._reconnection_attempts < 0:
            raise ValueError("reconnection_attempts must be a non-negative integer")

    @property
    def client_name(self) -> str:
        return self.__class__.__name__

    async def __aenter__(self) -> Self:
        # Don't handle any errors in the initial connection, because these are most
        # likely a permission or configuration issue that should propagate
        try:
            await self._reconnect()
        finally:
            EVENT_WEBSOCKET_CONNECTIONS.labels(self.client_name, "out", "initial")
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
        # Use the API key (for Cloud) OR the auth token (for self-hosted with auth string)
        token = self._api_key or self._auth_token
        await self._websocket.send(
            orjson.dumps({"type": "auth", "token": token}).decode()
        )

        try:
            message: Dict[str, Any] = orjson.loads(await self._websocket.recv())
            logger.debug("  auth result %s", message)
            assert message["type"] == "auth_success", message.get("reason", "")
        except AssertionError as e:
            raise Exception(
                "Unable to authenticate to the event stream. Please ensure the "
                "provided api_key or auth_token you are using is valid for this environment. "
                f"Reason: {e.args[0]}"
            )
        except ConnectionClosedError as e:
            reason = getattr(e.rcvd, "reason", None)
            msg = "Unable to authenticate to the event stream. Please ensure the "
            msg += "provided api_key or auth_token you are using is valid for this environment. "
            msg += f"Reason: {reason}" if reason else ""
            raise Exception(msg) from e

        from prefect.events.filters import EventOccurredFilter

        self._filter.occurred = EventOccurredFilter(
            since=prefect.types._datetime.now("UTC") - timedelta(minutes=1),
            until=prefect.types._datetime.now("UTC") + timedelta(days=365),
        )

        logger.debug("  filtering events since %s...", self._filter.occurred.since)
        filter_message = {
            "type": "filter",
            "filter": self._filter.model_dump(mode="json"),
        }
        await self._websocket.send(orjson.dumps(filter_message).decode())

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
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
                    try:
                        await self._reconnect()
                    finally:
                        EVENT_WEBSOCKET_CONNECTIONS.labels(
                            self.client_name, "out", "reconnect"
                        )
                    assert self._websocket

                while True:
                    message = orjson.loads(await self._websocket.recv())
                    event: Event = Event.model_validate(message["event"])

                    if event.id in self._seen_events:
                        continue
                    self._seen_events[event.id] = True

                    try:
                        return event
                    finally:
                        EVENTS_OBSERVED.labels(self.client_name).inc()
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
