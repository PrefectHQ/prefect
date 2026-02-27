"""Tests for PostgreSQL NOTIFY/LISTEN utilities."""

import ssl
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

    async def test_passes_full_dsn_to_asyncpg(self):
        """Test that the full DSN is passed as the first positional arg to asyncpg."""
        with temporary_settings(
            {PREFECT_API_DATABASE_CONNECTION_URL: "postgresql://user:pass@localhost/db"}
        ):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()
                # The DSN should be passed as the first positional arg
                dsn = mock_connect.call_args.args[0]
                assert dsn == "postgresql://user:pass@localhost/db"

    async def test_strips_asyncpg_dialect_from_dsn(self):
        """Test that +asyncpg dialect is stripped from the DSN."""
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: "postgresql+asyncpg://user:pass@localhost/db"
            }
        ):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                dsn = mock_connect.call_args.args[0]
                assert dsn.startswith("postgresql://")
                assert "+asyncpg" not in dsn

    async def test_unix_domain_socket_url_preserves_query_params(self):
        """Test that UNIX domain socket URLs with host/port in query params are
        preserved in the DSN passed to asyncpg."""
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: "postgresql+asyncpg:///prefect?host=/tmp/.SOSHUB&port=25432"
            }
        ):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()
                dsn = mock_connect.call_args.args[0]
                # The DSN should contain the query params for asyncpg to parse.
                # SQLAlchemy URL-encodes slashes in query param values.
                assert "host=%2Ftmp%2F.SOSHUB" in dsn
                assert "port=25432" in dsn
                assert dsn.startswith("postgresql:///")

    async def test_unix_domain_socket_url_without_port(self):
        """Test that UNIX domain socket URLs without port still work."""
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: "postgresql+asyncpg:///mydb?host=/var/run/postgresql"
            }
        ):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()
                dsn = mock_connect.call_args.args[0]
                # SQLAlchemy URL-encodes slashes in query param values
                assert "host=%2Fvar%2Frun%2Fpostgresql" in dsn
                assert "port" not in dsn

    async def test_standard_tcp_url_still_works(self):
        """Test that standard TCP URLs with host in authority section still work."""
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: "postgresql+asyncpg://user:pass@myhost:5433/mydb"
            }
        ):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()
                dsn = mock_connect.call_args.args[0]
                assert "user:pass@myhost:5433/mydb" in dsn
                assert dsn.startswith("postgresql://")

    async def test_preserves_kerberos_query_params(self):
        """Test that Kerberos-related query params (e.g. krbsrvname) are preserved
        in the DSN passed to asyncpg."""
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: "postgresql+asyncpg://user@myhost/mydb?krbsrvname=postgres"
            }
        ):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()
                dsn = mock_connect.call_args.args[0]
                assert "krbsrvname=postgres" in dsn
                assert "+asyncpg" not in dsn

    async def test_includes_tls_ssl_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that TLS/SSL context is passed to asyncpg when TLS is enabled."""
        monkeypatch.setenv(
            "PREFECT_SERVER_DATABASE_SQLALCHEMY_CONNECT_ARGS_TLS_ENABLED",
            "true",
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
                assert "ssl" in call_kwargs
                ssl_ctx = call_kwargs["ssl"]
                assert isinstance(ssl_ctx, ssl.SSLContext)
                assert ssl_ctx.verify_mode == ssl.CERT_REQUIRED

    async def test_excludes_tls_ssl_when_not_configured(self):
        """Test that ssl is not added when TLS is not enabled."""
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
                assert "ssl" not in call_kwargs
