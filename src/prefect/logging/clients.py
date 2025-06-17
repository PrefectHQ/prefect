import asyncio
from datetime import timedelta
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    MutableMapping,
    Optional,
    Tuple,
    Type,
    cast,
)
from uuid import UUID

import orjson
from cachetools import TTLCache
from prometheus_client import Counter
from typing_extensions import Self
from websockets import Subprotocol
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
)

from prefect._internal.websockets import (
    create_ssl_context_for_websocket,
    websocket_connect,
)
from prefect.client.schemas.objects import Log
from prefect.logging import get_logger
from prefect.settings import (
    PREFECT_API_AUTH_STRING,
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    PREFECT_SERVER_ALLOW_EPHEMERAL_MODE,
)
from prefect.types._datetime import now

if TYPE_CHECKING:
    import logging

    from prefect.client.schemas.filters import LogFilter

logger: "logging.Logger" = get_logger(__name__)

LOGS_OBSERVED = Counter(
    "prefect_logs_observed",
    "The number of logs observed by Prefect log subscribers",
    labelnames=["client"],
)
LOG_WEBSOCKET_CONNECTIONS = Counter(
    "prefect_log_websocket_connections",
    (
        "The number of times Prefect log clients have connected to a log stream, "
        "broken down by direction (in/out) and connection (initial/reconnect)"
    ),
    labelnames=["client", "direction", "connection"],
)

SEEN_LOGS_SIZE = 500_000
SEEN_LOGS_TTL = 120


def http_to_ws(url: str) -> str:
    return url.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")


def logs_out_socket_from_api_url(url: str) -> str:
    return http_to_ws(url) + "/logs/out"


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


def get_logs_subscriber(
    filter: Optional["LogFilter"] = None,
    reconnection_attempts: int = 10,
) -> "PrefectLogsSubscriber":
    """
    Get a logs subscriber based on the current Prefect configuration.

    Similar to get_events_subscriber, this automatically detects whether
    you're using Prefect Cloud or OSS and returns the appropriate subscriber.
    """
    api_url = PREFECT_API_URL.value()

    if isinstance(api_url, str) and api_url.startswith(PREFECT_CLOUD_API_URL.value()):
        return PrefectCloudLogsSubscriber(
            filter=filter, reconnection_attempts=reconnection_attempts
        )
    elif api_url:
        return PrefectLogsSubscriber(
            api_url=api_url,
            filter=filter,
            reconnection_attempts=reconnection_attempts,
        )
    elif PREFECT_SERVER_ALLOW_EPHEMERAL_MODE:
        from prefect.server.api.server import SubprocessASGIServer

        server = SubprocessASGIServer()
        server.start()
        return PrefectLogsSubscriber(
            api_url=server.api_url,
            filter=filter,
            reconnection_attempts=reconnection_attempts,
        )
    else:
        raise ValueError(
            "No Prefect API URL provided. Please set PREFECT_API_URL to the address of a running Prefect server."
        )


class PrefectLogsSubscriber:
    """
    Subscribes to a Prefect logs stream, yielding logs as they occur.

    Example:

        from prefect.logging.clients import PrefectLogsSubscriber
        from prefect.client.schemas.filters import LogFilter, LogFilterLevel
        import logging

        filter = LogFilter(level=LogFilterLevel(ge_=logging.INFO))

        async with PrefectLogsSubscriber(filter=filter) as subscriber:
            async for log in subscriber:
                print(log.timestamp, log.level, log.message)

    """

    _websocket: Optional[ClientConnection]
    _filter: "LogFilter"
    _seen_logs: MutableMapping[UUID, bool]

    _api_key: Optional[str]
    _auth_token: Optional[str]

    def __init__(
        self,
        api_url: Optional[str] = None,
        filter: Optional["LogFilter"] = None,
        reconnection_attempts: int = 10,
    ):
        """
        Args:
            api_url: The base URL for a Prefect workspace
            filter: Log filter to apply
            reconnection_attempts: When the client is disconnected, how many times
                the client should attempt to reconnect
        """
        self._api_key = None
        self._auth_token = PREFECT_API_AUTH_STRING.value()

        if not api_url:
            api_url = cast(str, PREFECT_API_URL.value())

        from prefect.client.schemas.filters import LogFilter

        self._filter = filter or LogFilter()  # type: ignore[call-arg]
        self._seen_logs = TTLCache(maxsize=SEEN_LOGS_SIZE, ttl=SEEN_LOGS_TTL)

        socket_url = logs_out_socket_from_api_url(api_url)

        logger.debug("Connecting to %s", socket_url)

        # Configure SSL context for the connection
        ssl_context = create_ssl_context_for_websocket(socket_url)
        connect_kwargs: dict[str, Any] = {"subprotocols": [Subprotocol("prefect")]}
        if ssl_context:
            connect_kwargs["ssl"] = ssl_context

        self._connect = websocket_connect(socket_url, **connect_kwargs)
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
            LOG_WEBSOCKET_CONNECTIONS.labels(self.client_name, "out", "initial").inc()
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

        # Send authentication message - logs WebSocket requires auth handshake
        auth_token = self._api_key or self._auth_token
        auth_message = {"type": "auth", "token": auth_token}
        logger.debug("  authenticating...")
        await self._websocket.send(orjson.dumps(auth_message).decode())

        # Wait for auth response
        try:
            message = orjson.loads(await self._websocket.recv())
            logger.debug("  auth result %s", message)
            assert message["type"] == "auth_success", message.get("reason", "")
        except AssertionError as e:
            raise Exception(
                "Unable to authenticate to the log stream. Please ensure the "
                "provided api_key or auth_token you are using is valid for this environment. "
                f"Reason: {e.args[0]}"
            )
        except ConnectionClosedError as e:
            reason = getattr(e.rcvd, "reason", None)
            msg = "Unable to authenticate to the log stream. Please ensure the "
            msg += "provided api_key or auth_token you are using is valid for this environment. "
            msg += f"Reason: {reason}" if reason else ""
            raise Exception(msg) from e

        from prefect.client.schemas.filters import LogFilterTimestamp

        current_time = now("UTC")
        self._filter.timestamp = LogFilterTimestamp(
            after_=current_time - timedelta(minutes=1),  # type: ignore[arg-type]
            before_=current_time + timedelta(days=365),  # type: ignore[arg-type]
        )

        logger.debug("  filtering logs since %s...", self._filter.timestamp.after_)
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

    async def __anext__(self) -> Log:
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
                        LOG_WEBSOCKET_CONNECTIONS.labels(
                            self.client_name, "out", "reconnect"
                        ).inc()
                    assert self._websocket

                while True:
                    message = orjson.loads(await self._websocket.recv())
                    log: Log = Log.model_validate(message["log"])

                    if log.id in self._seen_logs:
                        continue
                    self._seen_logs[log.id] = True

                    try:
                        return log
                    finally:
                        LOGS_OBSERVED.labels(self.client_name).inc()

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


class PrefectCloudLogsSubscriber(PrefectLogsSubscriber):
    """Logs subscriber for Prefect Cloud"""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        filter: Optional["LogFilter"] = None,
        reconnection_attempts: int = 10,
    ):
        """
        Args:
            api_url: The base URL for a Prefect Cloud workspace
            api_key: The API key of an actor with the see_flows scope
            filter: Log filter to apply
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
