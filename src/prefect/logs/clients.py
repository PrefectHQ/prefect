import asyncio
import os
import ssl
from datetime import timedelta
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    Generator,
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
from prefect.client.schemas.objects import Log
from prefect.logging import get_logger
from prefect.settings import (
    PREFECT_API_AUTH_STRING,
    PREFECT_API_KEY,
    PREFECT_API_SSL_CERT_FILE,
    PREFECT_API_TLS_INSECURE_SKIP_VERIFY,
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    PREFECT_SERVER_ALLOW_EPHEMERAL_MODE,
)

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

        from prefect.logs.clients import PrefectLogsSubscriber
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
        if not auth_token:
            raise ValueError("No API key or auth token available for authentication")

        auth_message = {
            "type": "auth",
            "token": auth_token,
        }
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

        self._filter.timestamp = LogFilterTimestamp(
            after_=prefect.types._datetime.now("UTC") - timedelta(minutes=1),
            before_=prefect.types._datetime.now("UTC") + timedelta(days=365),
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
