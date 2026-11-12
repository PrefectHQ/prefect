"""
Tests for prefect.testing.fixtures module.
"""

import asyncio
import subprocess
from contextlib import asynccontextmanager
from unittest import mock

import httpx
import pytest

from prefect.testing import fixtures

pytestmark = pytest.mark.clear_db


class TestHostedApiServerWindowsProcessHandling:
    """Tests for Windows-specific process handling in hosted_api_server fixture."""

    @pytest.mark.unix
    async def test_unix_hosted_api_server_does_not_set_creation_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """
        On Unix-like systems, the hosted_api_server fixture should NOT set
        creationflags since it's a Windows-only parameter.
        """
        captured_kwargs: dict = {}
        mock_process = mock.MagicMock()
        mock_process.returncode = 0
        mock_process.pid = 12345
        mock_process.terminate = mock.MagicMock()

        @asynccontextmanager
        async def mock_open_process(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield mock_process

        monkeypatch.setattr(fixtures, "open_process", mock_open_process)

        # Mock the HTTP client to simulate server ready
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = mock.MagicMock()

        mock_client = mock.MagicMock()
        mock_client.get = mock.AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mock.AsyncMock(return_value=None)

        monkeypatch.setattr("httpx.AsyncClient", lambda: mock_client)

        # Call the underlying generator function directly (not as a fixture)
        gen = fixtures.hosted_api_server.__wrapped__(
            unused_tcp_port_factory=lambda: 8000,
            test_database_connection_url=None,
        )
        await gen.__anext__()  # Start the fixture

        # Verify open_process was called without creationflags
        assert "creationflags" not in captured_kwargs

    @pytest.mark.windows
    async def test_windows_hosted_api_server_sets_process_group_creation_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """
        On Windows, the hosted_api_server fixture should create the uvicorn process
        with CREATE_NEW_PROCESS_GROUP flag so that the entire process tree can be
        terminated properly during teardown.
        """
        captured_kwargs: dict = {}
        mock_process = mock.MagicMock()
        mock_process.returncode = 0
        mock_process.pid = 12345

        @asynccontextmanager
        async def mock_open_process(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield mock_process

        monkeypatch.setattr(fixtures, "open_process", mock_open_process)

        # Mock the HTTP client to simulate server ready
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = mock.MagicMock()

        mock_client = mock.MagicMock()
        mock_client.get = mock.AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mock.AsyncMock(return_value=None)

        monkeypatch.setattr("httpx.AsyncClient", lambda: mock_client)

        # Call the underlying generator function directly (not as a fixture)
        gen = fixtures.hosted_api_server.__wrapped__(
            unused_tcp_port_factory=lambda: 8000,
            test_database_connection_url=None,
        )
        await gen.__anext__()  # Start the fixture

        # Verify open_process was called with creationflags
        assert "creationflags" in captured_kwargs
        assert captured_kwargs["creationflags"] == subprocess.CREATE_NEW_PROCESS_GROUP

    @pytest.mark.unix
    async def test_unix_hosted_api_server_uses_terminate_for_shutdown(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """
        On Unix-like systems, the hosted_api_server fixture should use
        process.terminate() for graceful shutdown.
        """
        mock_process = mock.MagicMock()
        mock_process.returncode = None  # Process still running initially
        mock_process.pid = 12345
        mock_process.terminate = mock.MagicMock()
        mock_process.kill = mock.MagicMock()

        # Make terminate set returncode to simulate process exit
        def set_returncode():
            mock_process.returncode = 0

        mock_process.terminate.side_effect = set_returncode

        @asynccontextmanager
        async def mock_open_process(*args, **kwargs):
            yield mock_process

        monkeypatch.setattr(fixtures, "open_process", mock_open_process)

        # Mock the HTTP client to simulate server ready
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = mock.MagicMock()

        mock_client = mock.MagicMock()
        mock_client.get = mock.AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mock.AsyncMock(return_value=None)

        monkeypatch.setattr("httpx.AsyncClient", lambda: mock_client)

        # Call the underlying generator function directly (not as a fixture)
        gen = fixtures.hosted_api_server.__wrapped__(
            unused_tcp_port_factory=lambda: 8000,
            test_database_connection_url=None,
        )
        await gen.__anext__()  # Start the fixture
        try:
            await gen.__anext__()  # Trigger teardown
        except StopAsyncIteration:
            pass

        # Verify process.terminate() was called
        mock_process.terminate.assert_called_once()


class TestHostedApiServerPortAllocation:
    @pytest.mark.unix
    async def test_hosted_api_server_is_not_shadowed_by_server_on_probed_port(
        self,
    ):
        """
        Another process (e.g. another xdist worker's API server) can bind a port
        after it was probed as free. The fixture must still yield the URL of
        its own API server instead of whichever server holds that port.
        """

        async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            await reader.readuntil(b"\r\n\r\n")
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Length: 7\r\n"
                b"Content-Type: application/json\r\n"
                b"Connection: close\r\n\r\n"
                b'"other"'
            )
            await writer.drain()
            writer.close()

        other_server = await asyncio.start_server(handle, "127.0.0.1", 0)
        taken_port = other_server.sockets[0].getsockname()[1]

        async with other_server:
            gen = fixtures.hosted_api_server.__wrapped__(
                unused_tcp_port_factory=lambda: taken_port,
                test_database_connection_url=None,
            )
            api_url = await gen.__anext__()
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{api_url}/hello")
                assert response.json() == "👋"
            finally:
                with pytest.raises(StopAsyncIteration):
                    await gen.__anext__()  # Trigger teardown
