"""
Internal WebSocket proxy utilities for Prefect client connections.

This module provides shared WebSocket proxy connection logic to avoid
duplication between events and logs clients.
"""

import os
from typing import Any, Generator
from urllib.parse import urlparse
from urllib.request import proxy_bypass

from python_socks.async_.asyncio import Proxy
from typing_extensions import Self
from websockets.asyncio.client import ClientConnection, connect


class WebsocketProxyConnect(connect):
    """
    WebSocket connection class with proxy support.

    Extends the websockets.asyncio.client.connect class to add HTTP/HTTPS
    proxy support via environment variables and proxy bypass logic.
    """

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
    """Create a WebSocket connection with proxy support."""
    return WebsocketProxyConnect(uri, **kwargs)
