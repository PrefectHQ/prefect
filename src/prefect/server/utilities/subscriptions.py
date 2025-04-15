import asyncio
from asyncio import IncompleteReadError as IOError
from logging import Logger
from typing import Optional

from fastapi import WebSocket
from starlette.status import WS_1002_PROTOCOL_ERROR, WS_1008_POLICY_VIOLATION
from starlette.websockets import WebSocketDisconnect
from websockets.exceptions import ConnectionClosed

from prefect.logging import get_logger
from prefect.settings import get_current_settings

NORMAL_DISCONNECT_EXCEPTIONS = (IOError, ConnectionClosed, WebSocketDisconnect)

logger: Logger = get_logger("prefect.server.utilities.subscriptions")


async def accept_prefect_socket(websocket: WebSocket) -> Optional[WebSocket]:
    subprotocols = websocket.headers.get("Sec-WebSocket-Protocol", "").split(",")
    if "prefect" not in subprotocols:
        return await websocket.close(WS_1002_PROTOCOL_ERROR)

    await websocket.accept(subprotocol="prefect")

    try:
        # Websocket connections are authenticated via messages. The first
        # message is expected to be an auth message, and if any other type of
        # message is received then the connection will be closed.
        #
        # The protocol requires receiving an auth message for compatibility
        # with Prefect Cloud, even if server-side auth is not configured.
        message = await websocket.receive_json()

        auth_setting = (
            auth_setting_secret.get_secret_value()
            if (auth_setting_secret := get_current_settings().server.api.auth_string)
            else None
        )
        logger.debug(
            f"PREFECT_SERVER_API_AUTH_STRING setting: {'*' * len(auth_setting) if auth_setting else 'Not set'}"
        )

        if message.get("type") != "auth":
            logger.warning(
                "WebSocket connection closed: Expected 'auth' message first."
            )
            return await websocket.close(
                WS_1008_POLICY_VIOLATION, reason="Expected 'auth' message"
            )

        # Check authentication if PREFECT_SERVER_API_AUTH_STRING is set
        if auth_setting:
            received_token = message.get("token")
            logger.debug(
                f"Auth required. Received token: {'*' * len(received_token) if received_token else 'None'}"
            )
            if not received_token:
                logger.warning(
                    "WebSocket connection closed: Auth required but no token received."
                )
                return await websocket.close(
                    WS_1008_POLICY_VIOLATION,
                    reason="Auth required but no token provided",
                )

            if received_token != auth_setting:
                logger.warning("WebSocket connection closed: Invalid token.")
                return await websocket.close(
                    WS_1008_POLICY_VIOLATION, reason="Invalid token"
                )
            logger.debug("WebSocket token authentication successful.")
        else:
            logger.debug("No server auth string set, skipping token check.")

        await websocket.send_json({"type": "auth_success"})
        logger.debug("Sent auth_success to WebSocket.")
        return websocket

    except NORMAL_DISCONNECT_EXCEPTIONS:
        # it's fine if a client disconnects either normally or abnormally
        return None


async def still_connected(websocket: WebSocket) -> bool:
    """Checks that a client websocket still seems to be connected during a period where
    the server is expected to be sending messages."""
    try:
        await asyncio.wait_for(websocket.receive(), timeout=0.1)
        return True  # this should never happen, but if it does, we're still connected
    except asyncio.TimeoutError:
        # The fact that we timed out rather than getting another kind of error
        # here means we're still connected to our client, so we can continue to send
        # events.
        return True
    except RuntimeError:
        # starlette raises this if we test a client that's disconnected
        return False
    except NORMAL_DISCONNECT_EXCEPTIONS:
        return False
