"""Tests for WebSocket proxy connection handling."""

import asyncio
import os
from unittest.mock import AsyncMock, Mock, patch

from prefect._internal.websockets import WebsocketProxyConnect


async def test_multiple_websocket_connections_with_proxy():
    """Test that multiple WebSocket connections through proxy don't cause loop conflicts."""
    # Set up proxy environment
    with patch.dict(os.environ, {"HTTPS_PROXY": "http://proxy:8080"}):
        # Mock the proxy and websocket internals
        mock_proxy = Mock()
        mock_proxy.connect = AsyncMock()

        # Create mock sockets
        import socket

        sock1 = Mock(spec=socket.socket)
        sock2 = Mock(spec=socket.socket)
        mock_proxy.connect.side_effect = [sock1, sock2]

        with patch(
            "prefect._internal.websockets.Proxy.from_url", return_value=mock_proxy
        ):
            with patch("prefect._internal.websockets.proxy_bypass", return_value=False):
                with patch(
                    "websockets.asyncio.client.connect.__await_impl__",
                    new_callable=AsyncMock,
                ) as mock_await:
                    mock_await.return_value = Mock()

                    # Create two connections sequentially
                    conn1 = WebsocketProxyConnect("wss://api.prefect.cloud/events/out")
                    result1 = await conn1

                    conn2 = WebsocketProxyConnect("wss://api.prefect.cloud/events/in")
                    result2 = await conn2

                    # Both should succeed without loop errors
                    assert result1 is not None
                    assert result2 is not None
                    assert mock_proxy.connect.call_count == 2


async def test_concurrent_websocket_connections_with_proxy():
    """Test concurrent WebSocket connections through proxy."""
    with patch.dict(os.environ, {"HTTPS_PROXY": "http://proxy:8080"}):
        mock_proxy = Mock()
        mock_proxy.connect = AsyncMock()

        import socket

        sock1 = Mock(spec=socket.socket)
        sock2 = Mock(spec=socket.socket)
        mock_proxy.connect.side_effect = [sock1, sock2]

        with patch(
            "prefect._internal.websockets.Proxy.from_url", return_value=mock_proxy
        ):
            with patch("prefect._internal.websockets.proxy_bypass", return_value=False):
                with patch(
                    "websockets.asyncio.client.connect.__await_impl__",
                    new_callable=AsyncMock,
                ) as mock_await:
                    mock_await.return_value = Mock()

                    # Create connections concurrently
                    conn1 = WebsocketProxyConnect("wss://api.prefect.cloud/events/out")
                    conn2 = WebsocketProxyConnect("wss://api.prefect.cloud/events/in")

                    results = await asyncio.gather(conn1, conn2)

                    assert len(results) == 2
                    assert all(r is not None for r in results)


async def test_websocket_connection_without_proxy():
    """Test WebSocket connections work normally without proxy."""
    # No proxy environment variables set
    with patch.dict(os.environ, {}, clear=True):
        with patch(
            "websockets.asyncio.client.connect.__await_impl__", new_callable=AsyncMock
        ) as mock_await:
            mock_await.return_value = Mock()

            conn = WebsocketProxyConnect("wss://api.prefect.cloud/events/out")
            result = await conn

            assert result is not None
            # No proxy connect should have been called


async def test_proxy_bypass():
    """Test that proxy bypass works correctly."""
    with patch.dict(os.environ, {"HTTPS_PROXY": "http://proxy:8080"}):
        # Mock proxy_bypass to return True (bypass proxy)
        with patch("prefect._internal.websockets.proxy_bypass", return_value=True):
            with patch(
                "websockets.asyncio.client.connect.__await_impl__",
                new_callable=AsyncMock,
            ) as mock_await:
                mock_await.return_value = Mock()

                # This should not use proxy even though HTTPS_PROXY is set
                conn = WebsocketProxyConnect("wss://localhost/events")
                result = await conn

                assert result is not None
                # Verify Proxy.from_url was never called since we bypassed
