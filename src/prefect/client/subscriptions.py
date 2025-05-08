import asyncio
from collections.abc import Iterable
from logging import Logger
from typing import Any, Generic, Optional, TypeVar

import orjson
import websockets
import websockets.asyncio.client
import websockets.exceptions
from starlette.status import WS_1008_POLICY_VIOLATION
from typing_extensions import Self

from prefect._internal.schemas.bases import IDBaseModel
from prefect.events.clients import websocket_connect
from prefect.logging import get_logger
from prefect.settings import get_current_settings

logger: Logger = get_logger(__name__)

S = TypeVar("S", bound=IDBaseModel)


class Subscription(Generic[S]):
    def __init__(
        self,
        model: type[S],
        path: str,
        keys: Iterable[str],
        client_id: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.model = model
        self.client_id = client_id
        base_url = base_url.replace("http", "ws", 1) if base_url else None
        self.subscription_url: str = f"{base_url}{path}"

        self.keys: list[str] = list(keys)

        self._connect = websocket_connect(
            self.subscription_url,
            subprotocols=[websockets.Subprotocol("prefect")],
        )
        self._websocket = None

    def __aiter__(self) -> Self:
        return self

    @property
    def websocket(self) -> websockets.asyncio.client.ClientConnection:
        if not self._websocket:
            raise RuntimeError("Subscription is not connected")
        return self._websocket

    async def __anext__(self) -> S:
        while True:
            try:
                await self._ensure_connected()
                message = await self.websocket.recv()

                await self.websocket.send(orjson.dumps({"type": "ack"}).decode())

                return self.model.model_validate_json(message)
            except (
                ConnectionRefusedError,
                websockets.exceptions.ConnectionClosedError,
            ):
                self._websocket = None
                if hasattr(self._connect, "protocol"):
                    await self._connect.__aexit__(None, None, None)
                await asyncio.sleep(0.5)

    async def _ensure_connected(self):
        if self._websocket:
            return

        websocket = await self._connect.__aenter__()

        try:
            settings = get_current_settings()
            auth_token = (
                settings.api.auth_string.get_secret_value()
                if settings.api.auth_string
                else None
            )
            api_key = settings.api.key.get_secret_value() if settings.api.key else None
            token = auth_token or api_key  # Prioritize auth_token

            await websocket.send(
                orjson.dumps({"type": "auth", "token": token}).decode()
            )

            auth: dict[str, Any] = orjson.loads(await websocket.recv())
            assert auth["type"] == "auth_success", auth.get("message")

            message: dict[str, Any] = {"type": "subscribe", "keys": self.keys}
            if self.client_id:
                message.update({"client_id": self.client_id})

            await websocket.send(orjson.dumps(message).decode())
        except (
            AssertionError,
            websockets.exceptions.ConnectionClosedError,
        ) as e:
            if isinstance(e, AssertionError) or (
                e.rcvd and e.rcvd.code == WS_1008_POLICY_VIOLATION
            ):
                if isinstance(e, AssertionError):
                    reason = e.args[0]
                elif e.rcvd and e.rcvd.reason:
                    reason = e.rcvd.reason
                else:
                    reason = "unknown"
            else:
                reason = None

            if reason:
                error_message = (
                    "Unable to authenticate to the subscription. Please ensure the provided "
                    "`PREFECT_API_AUTH_STRING` (for self-hosted with auth string) or "
                    "`PREFECT_API_KEY` (for Cloud or self-hosted with API key) "
                    f"you are using is valid for this environment. Reason: {reason}"
                )
                raise Exception(error_message) from e
            raise
        else:
            self._websocket = websocket

    def __repr__(self) -> str:
        return f"{type(self).__name__}[{self.model.__name__}]"
