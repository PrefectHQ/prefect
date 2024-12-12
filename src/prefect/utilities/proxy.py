import os
from typing import (
    Any,
    Generator,
)
from urllib.parse import urlparse

from python_socks.async_.asyncio import Proxy
from typing_extensions import Self
from websockets.client import WebSocketClientProtocol
from websockets.legacy.client import Connect


class WebsocketProxyConnect(Connect):
    def __init__(self: Self, uri: str, **kwargs: Any):
        # super() is intentionally deferred to the __proxy_connect__ method
        # to allow for the proxy to be established before the connection is made

        self.uri = uri
        self.__kwargs = kwargs

        u = urlparse(uri)
        host = u.hostname

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

        self.__proxy = Proxy.from_url(proxy_url) if proxy_url else None
        self.__host = host
        self.__port = port

    async def __proxy_connect__(self: Self) -> WebSocketClientProtocol:
        if self.__proxy:
            sock = await self.__proxy.connect(
                dest_host=self.__host,
                dest_port=self.__port,
            )
            self.__kwargs["sock"] = sock

        super().__init__(self.uri, **self.__kwargs)
        proto = await self.__await_impl__()
        return proto

    def __await__(self: Self) -> Generator[Any, None, WebSocketClientProtocol]:
        return self.__proxy_connect__().__await__()


def websocket_connect(uri: str, **kwargs: Any) -> WebsocketProxyConnect:
    return WebsocketProxyConnect(uri, **kwargs)
