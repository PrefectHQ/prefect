"""Tests for PostgreSQL NOTIFY/LISTEN utilities."""

from unittest import mock
from unittest.mock import AsyncMock, MagicMock

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
