import asyncio
from typing import Generic, List, Type, TypeVar

import orjson
import websockets
import websockets.exceptions
from prefect._vendor.starlette.status import WS_1008_POLICY_VIOLATION
from typing_extensions import Self

from prefect._internal.schemas.bases import IDBaseModel
from prefect.logging import get_logger
from prefect.settings import PREFECT_API_KEY, PREFECT_API_URL

logger = get_logger(__name__)

S = TypeVar("S", bound=IDBaseModel)


class Subscription(Generic[S]):
    def __init__(self, model: Type[S], path: str, keys: List[str]):
        self.model = model

        base_url = PREFECT_API_URL.value().replace("http", "ws", 1)
        self.subscription_url = f"{base_url}{path}"

        self.keys = keys

        self._connect = websockets.connect(
            self.subscription_url,
            subprotocols=["prefect"],
        )
        self._websocket = None

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> S:
        while True:
            try:
                await self._ensure_connected()
                message = await self._websocket.recv()

                await self._websocket.send(orjson.dumps({"type": "ack"}).decode())

                return self.model.parse_raw(message)
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
            await websocket.send(
                orjson.dumps(
                    {"type": "auth", "token": PREFECT_API_KEY.value()}
                ).decode()
            )

            auth = orjson.loads(await websocket.recv())
            assert auth["type"] == "auth_success"

            await websocket.send(
                orjson.dumps({"type": "subscribe", "keys": self.keys}).decode()
            )
        except (
            AssertionError,
            websockets.exceptions.ConnectionClosedError,
        ) as e:
            if isinstance(e, AssertionError) or e.code == WS_1008_POLICY_VIOLATION:
                raise Exception(
                    "Unable to authenticate to the subscription. Please "
                    "ensure the provided `PREFECT_API_KEY` you are using is "
                    "valid for this environment."
                ) from e
            raise
        else:
            self._websocket = websocket

    def __repr__(self) -> str:
        return f"{type(self).__name__}[{self.model.__name__}]"
