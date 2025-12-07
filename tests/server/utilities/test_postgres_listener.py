"""Tests for PostgreSQL NOTIFY/LISTEN utilities."""

from unittest import mock
from unittest.mock import AsyncMock, MagicMock

import pytest

from prefect.server.utilities.postgres_listener import (
    get_pg_notify_connection,
)
from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL, temporary_settings


class TestGetPgNotifyConnection:
    """Tests for get_pg_notify_connection function."""

    async def test_returns_none_for_non_postgres_url(self):
        """Test that non-PostgreSQL URLs return None."""
        with temporary_settings(
            {PREFECT_API_DATABASE_CONNECTION_URL: "sqlite:///test.db"}
        ):
            conn = await get_pg_notify_connection()
            assert conn is None

    async def test_attempts_connection_for_postgres_urls(self):
        """Test that PostgreSQL URLs attempt to connect."""
        with temporary_settings(
            {PREFECT_API_DATABASE_CONNECTION_URL: "postgresql://user:pass@localhost/db"}
        ):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()

    async def test_handles_connection_failure(self):
        """Test that connection failures are handled gracefully."""
        with temporary_settings(
            {PREFECT_API_DATABASE_CONNECTION_URL: "postgresql://localhost/test"}
        ):
            with mock.patch(
                "asyncpg.connect", side_effect=Exception("Connection failed")
            ):
                conn = await get_pg_notify_connection()
                assert conn is None

    async def test_includes_application_name_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that application_name is passed to asyncpg when configured."""
        monkeypatch.setenv(
            "PREFECT_SERVER_DATABASE_SQLALCHEMY_CONNECT_ARGS_APPLICATION_NAME",
            "test-app-name",
        )
        with temporary_settings(
            {PREFECT_API_DATABASE_CONNECTION_URL: "postgresql://user:pass@localhost/db"}
        ):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()
                call_kwargs = mock_connect.call_args.kwargs
                assert "server_settings" in call_kwargs
                assert (
                    call_kwargs["server_settings"]["application_name"]
                    == "test-app-name"
                )

    async def test_excludes_application_name_when_not_configured(self):
        """Test that server_settings is not added when application_name is not configured."""
        with temporary_settings(
            {PREFECT_API_DATABASE_CONNECTION_URL: "postgresql://user:pass@localhost/db"}
        ):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()
                call_kwargs = mock_connect.call_args.kwargs
                assert "server_settings" not in call_kwargs

    async def test_includes_search_path_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that search_path is passed to asyncpg when configured."""
        monkeypatch.setenv(
            "PREFECT_SERVER_DATABASE_SQLALCHEMY_CONNECT_ARGS_SEARCH_PATH",
            "myschema",
        )
        with temporary_settings(
            {PREFECT_API_DATABASE_CONNECTION_URL: "postgresql://user:pass@localhost/db"}
        ):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()
                call_kwargs = mock_connect.call_args.kwargs
                assert "server_settings" in call_kwargs
                assert call_kwargs["server_settings"]["search_path"] == "myschema"

    async def test_includes_both_application_name_and_search_path_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that both application_name and search_path are passed when configured."""
        monkeypatch.setenv(
            "PREFECT_SERVER_DATABASE_SQLALCHEMY_CONNECT_ARGS_APPLICATION_NAME",
            "test-app-name",
        )
        monkeypatch.setenv(
            "PREFECT_SERVER_DATABASE_SQLALCHEMY_CONNECT_ARGS_SEARCH_PATH",
            "myschema",
        )
        with temporary_settings(
            {PREFECT_API_DATABASE_CONNECTION_URL: "postgresql://user:pass@localhost/db"}
        ):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()
                call_kwargs = mock_connect.call_args.kwargs
                assert "server_settings" in call_kwargs
                assert (
                    call_kwargs["server_settings"]["application_name"]
                    == "test-app-name"
                )
                assert call_kwargs["server_settings"]["search_path"] == "myschema"
