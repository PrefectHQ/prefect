"""
Internal WebSocket proxy utilities for Prefect client connections.

This module provides shared WebSocket proxy connection logic and SSL configuration
to avoid duplication between events and logs clients.
"""

import ssl
import warnings
from functools import wraps
from typing import Any, Optional
from urllib.parse import urlparse

import certifi
from websockets.asyncio.client import connect

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


@wraps(connect)
def websocket_connect(uri: str, **kwargs: Any) -> connect:
    """
    Create a WebSocket connection with proxy and SSL support.

    Proxy support is automatic via HTTP_PROXY/HTTPS_PROXY environment variables.
    The websockets library handles proxy detection and connection automatically.
    """
    # Configure SSL context for HTTPS connections
    ssl_context = create_ssl_context_for_websocket(uri)
    if ssl_context:
        kwargs.setdefault("ssl", ssl_context)

    # Add custom headers from settings
    custom_headers = get_current_settings().client.custom_headers
    if custom_headers:
        # Get existing additional_headers or create new dict
        additional_headers = kwargs.get("additional_headers", {})
        if not isinstance(additional_headers, dict):
            additional_headers = {}

        for header_name, header_value in custom_headers.items():
            # Check for protected headers that shouldn't be overridden
            if header_name.lower() in {
                "user-agent",
                "sec-websocket-key",
                "sec-websocket-version",
                "sec-websocket-extensions",
                "sec-websocket-protocol",
                "connection",
                "upgrade",
                "host",
            }:
                warnings.warn(
                    f"Custom header '{header_name}' is ignored because it conflicts with "
                    f"a protected WebSocket header. Protected headers include: "
                    f"User-Agent, Sec-WebSocket-Key, Sec-WebSocket-Version, "
                    f"Sec-WebSocket-Extensions, Sec-WebSocket-Protocol, Connection, "
                    f"Upgrade, Host",
                    UserWarning,
                    stacklevel=2,
                )
            else:
                additional_headers[header_name] = header_value

        kwargs["additional_headers"] = additional_headers

    return connect(uri, **kwargs)
