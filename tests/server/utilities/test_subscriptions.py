from starlette.types import Message
from starlette.websockets import WebSocket, WebSocketState

from prefect.server.utilities.subscriptions import still_connected


def connected_websocket(message: Message) -> WebSocket:
    async def receive() -> Message:
        return message

    async def send(message: Message) -> None:
        raise AssertionError("still_connected should not send")

    websocket = WebSocket(
        {"type": "websocket", "path": "/", "headers": []}, receive, send
    )
    websocket.client_state = WebSocketState.CONNECTED
    return websocket


class TestStillConnected:
    async def test_false_after_disconnect_message(self):
        websocket = connected_websocket({"type": "websocket.disconnect", "code": 1001})

        assert not await still_connected(websocket)

    async def test_true_after_client_message(self):
        websocket = connected_websocket({"type": "websocket.receive", "text": "hi"})

        assert await still_connected(websocket)
