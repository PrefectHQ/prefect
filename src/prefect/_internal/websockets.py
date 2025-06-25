"""
Internal WebSocket proxy utilities for Prefect client connections.

This module provides shared WebSocket proxy connection logic and SSL configuration
to avoid duplication between events and logs clients.
"""

import os
import ssl
from typing import Any, Generator, Optional
from urllib.parse import urlparse
from urllib.request import proxy_bypass

import certifi
from python_socks.async_.asyncio import Proxy
from typing_extensions import Self
from websockets.asyncio.client import ClientConnection, connect

from prefect.settings import get_current_settings


def create_ssl_context_for_websocket(uri: str) -> Optional[ssl.SSLContext]:
    """Create SSL context for WebSocket connections based on URI scheme."""
    u = urlparse(uri)

    if u.scheme != "wss":
        return None

    if get_current_settings().api.tls_insecure_skip_verify:
        # Create an unverified context for insecure connections
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    else:
        # Create a verified context with the certificate file
        cert_file = get_current_settings().api.ssl_cert_file
        if not cert_file:
            cert_file = certifi.where()
        return ssl.create_default_context(cafile=cert_file)


class WebsocketProxyConnect(connect):
    """
    WebSocket connection class with proxy and SSL support.

    Extends the websockets.asyncio.client.connect class to add HTTP/HTTPS
    proxy support via environment variables, proxy bypass logic, and SSL
    certificate verification.
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

        # Store proxy URL for deferred creation. Creating the proxy object here
        # can bind asyncio futures to the wrong event loop when multiple WebSocket
        # connections are initialized at different times (e.g., events + logs clients).
        self._proxy_url = proxy_url if proxy_url and not proxy_bypass(host) else None
        self._host = host
        self._port = port

        # Configure SSL context for HTTPS connections
        ssl_context = create_ssl_context_for_websocket(uri)
        if ssl_context:
            self._kwargs.setdefault("ssl", ssl_context)

    async def _proxy_connect(self: Self) -> ClientConnection:
        if self._proxy_url:
            # Create proxy in the current event loop context
            proxy = Proxy.from_url(self._proxy_url)
            sock = await proxy.connect(
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
    """Create a WebSocket connection with proxy and SSL support."""
    return WebsocketProxyConnect(uri, **kwargs)
