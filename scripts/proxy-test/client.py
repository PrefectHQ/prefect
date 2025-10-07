import asyncio
import os

from prefect.events.clients import websocket_connect

PROXY_URL = "http://localhost:3128"
WS_SERVER_URL = "ws://server:8000/ws"


async def test_websocket_proxy_via_environment() -> None:
    """Connect through an HTTP proxy discovered via environment variables."""
    os.environ["HTTP_PROXY"] = PROXY_URL

    async with websocket_connect(WS_SERVER_URL) as websocket:
        message = "Hello!"
        await websocket.send(message)
        response = await websocket.recv()
        print("Response: ", response)
        assert response == f"Server received: {message}"


async def main():
    print("Testing WebSocket connection through proxy discovered via env vars")
    await test_websocket_proxy_via_environment()


if __name__ == "__main__":
    asyncio.run(main())
