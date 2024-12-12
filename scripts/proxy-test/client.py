import asyncio
import os

from prefect.utilities.proxy import websocket_connect

PROXY_URL = "http://localhost:3128"
WS_SERVER_URL = "ws://server:8000/ws"


async def test_websocket_proxy_with_compat():
    """WebSocket through proxy with proxy compatibility code - should work"""
    os.environ["HTTP_PROXY"] = "http://localhost:3128"

    async with websocket_connect("ws://server:8000/ws") as websocket:
        await websocket.send("Hello!")
        response = await websocket.recv()
        print("Response: ", response)
        assert response == "Server received: Hello!"


async def main():
    print("Testing WebSocket through proxy with compatibility code")
    await test_websocket_proxy_with_compat()


if __name__ == "__main__":
    asyncio.run(main())
