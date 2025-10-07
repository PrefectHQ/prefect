"""Internal WebSocket utilities for Prefect client connections."""

import ssl
import warnings
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import certifi
from websockets.asyncio.client import ClientConnection, connect

from prefect.settings import get_current_settings

_PROTECTED_HEADERS = {
    "user-agent",
    "sec-websocket-key",
    "sec-websocket-version",
    "sec-websocket-extensions",
    "sec-websocket-protocol",
    "connection",
    "upgrade",
    "host",
}


def create_ssl_context_for_websocket(uri: str) -> Optional[ssl.SSLContext]:
    """Create SSL context for WebSocket connections based on URI scheme."""

    u = urlparse(uri)

    if u.scheme != "wss":
        return None

    if get_current_settings().api.tls_insecure_skip_verify:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    cert_file = get_current_settings().api.ssl_cert_file or certifi.where()
    return ssl.create_default_context(cafile=cert_file)


def _merge_custom_headers(kwargs: Dict[str, Any]) -> None:
    """Merge Prefect custom headers into websockets kwargs."""

    custom_headers = get_current_settings().client.custom_headers
    if not custom_headers:
        return

    additional_headers = kwargs.get("additional_headers")
    if additional_headers is None:
        additional_headers = {}
    elif not isinstance(additional_headers, dict):
        additional_headers = dict(additional_headers)

    for header_name, header_value in custom_headers.items():
        if header_name.lower() in _PROTECTED_HEADERS:
            warnings.warn(
                (
                    f"Custom header '{header_name}' is ignored because it conflicts with "
                    "a protected WebSocket header. Protected headers include: "
                    "User-Agent, Sec-WebSocket-Key, Sec-WebSocket-Version, "
                    "Sec-WebSocket-Extensions, Sec-WebSocket-Protocol, Connection, "
                    "Upgrade, Host"
                ),
                UserWarning,
                stacklevel=2,
            )
            continue

        additional_headers[header_name] = header_value

    if additional_headers:
        kwargs["additional_headers"] = additional_headers


def websocket_connect(uri: str, **kwargs: Any) -> ClientConnection:
    """Create a WebSocket connection with Prefect-specific configuration."""

    if "ssl" not in kwargs:
        ssl_context = create_ssl_context_for_websocket(uri)
        if ssl_context:
            kwargs["ssl"] = ssl_context

    _merge_custom_headers(kwargs)

    return connect(uri, **kwargs)
