"""
Tests for prefect.testing.fixtures module.
"""

import subprocess
from contextlib import asynccontextmanager
from unittest import mock

import pytest

from prefect.testing import fixtures


class TestHostedApiServerWindowsProcessHandling:
    """Tests for Windows-specific process handling in hosted_api_server fixture."""

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
