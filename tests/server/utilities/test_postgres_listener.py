"""Tests for PostgreSQL NOTIFY/LISTEN utilities."""

import ssl
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock, MagicMock

import pytest
from asyncpg import connect_utils

from prefect.server.utilities.postgres_listener import (
    get_pg_notify_connection,
)
from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL, temporary_settings


def _parse_asyncpg_dsn(dsn: str) -> tuple[list[Any], Any]:
    addrs, params, _config = connect_utils._parse_connect_arguments(
        dsn=dsn,
        host=None,
        port=None,
        user=None,
        password=None,
        passfile=None,
        database=None,
        command_timeout=None,
        statement_cache_size=100,
        max_cached_statement_lifetime=300,
        max_cacheable_statement_size=15 * 1024,
        ssl=None,
        direct_tls=None,
        server_settings=None,
        target_session_attrs=None,
        krbsrvname=None,
        gsslib=None,
        service=None,
        servicefile=None,
    )
    return addrs, params


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
                # The DSN should contain the query params for asyncpg to parse,
                # with the original values preserved (no URL-encoding of slashes).
                assert "host=/tmp/.SOSHUB" in dsn
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
                # Original path is preserved without URL-encoding
                assert "host=/var/run/postgresql" in dsn
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

    async def test_multihost_connection_string_normalized_for_asyncpg(self):
        """Test that repeated multihost query params are normalized into the
        comma-separated form that asyncpg actually parses."""
        multihost_url = (
            "postgresql+asyncpg://user@/dbname"
            "?host=HostA:5432&host=HostB:5432&host=HostC:5432"
        )
        with temporary_settings({PREFECT_API_DATABASE_CONNECTION_URL: multihost_url}):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()
                dsn = mock_connect.call_args.args[0]
                # The dialect should be stripped
                assert dsn.startswith("postgresql://")
                assert "+asyncpg" not in dsn
                # asyncpg/libpq expects multihost query params as comma-separated
                # lists, not repeated keys.
                assert "host=HostA:5432,HostB:5432,HostC:5432" in dsn
                assert dsn.count("host=") == 1
                assert "%3A" not in dsn
                addrs, _ = _parse_asyncpg_dsn(dsn)
                assert addrs == [
                    ("HostA", 5432),
                    ("HostB", 5432),
                    ("HostC", 5432),
                ]

    async def test_multihost_with_extra_params_preserved(self):
        """Test that multihost connection strings with additional params like
        target_session_attrs, gsslib, krbsrvname, and sslmode are preserved."""
        multihost_url = (
            "postgresql+asyncpg://user@/dbname"
            "?host=HostA:5432&host=HostB:5432&host=HostC:5432"
            "&gsslib=gssapi&krbsrvname=postgresql&ssl=require"
            "&target_session_attrs=primary"
        )
        with temporary_settings({PREFECT_API_DATABASE_CONNECTION_URL: multihost_url}):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()
                dsn = mock_connect.call_args.args[0]
                assert dsn.startswith("postgresql://")
                # Repeated multihost params are collapsed into asyncpg's
                # supported comma-separated form.
                assert "host=HostA:5432,HostB:5432,HostC:5432" in dsn
                assert dsn.count("host=") == 1
                # Additional connection params preserved
                assert "gsslib=gssapi" in dsn
                assert "krbsrvname=postgresql" in dsn
                assert "sslmode=require" in dsn
                assert "ssl=require" not in dsn
                assert "target_session_attrs=primary" in dsn
                addrs, params = _parse_asyncpg_dsn(dsn)
                assert addrs == [
                    ("HostA", 5432),
                    ("HostB", 5432),
                    ("HostC", 5432),
                ]
                assert params.target_session_attrs.value == "primary"
                assert params.server_settings is None

    async def test_ssl_query_param_renamed_to_sslmode(self):
        """Test that the non-standard 'ssl' query parameter is renamed to 'sslmode'
        so asyncpg recognises it as a connection parameter instead of passing it
        through as a PostgreSQL server setting."""
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: "postgresql+asyncpg://user@host:5432/db?ssl=require"
            }
        ):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()
                dsn = mock_connect.call_args.args[0]
                assert "sslmode=require" in dsn
                assert "ssl=require" not in dsn

    async def test_ssl_query_param_with_kerberos_and_multihost(self):
        """Test that ssl is renamed to sslmode while preserving other params
        including multihost host:port pairs (colons must not be re-encoded)."""
        url = (
            "postgresql+asyncpg://user@/dbname"
            "?host=HostA:5432&host=HostB:5432"
            "&gsslib=gssapi&krbsrvname=postgresql&ssl=require"
        )
        with temporary_settings({PREFECT_API_DATABASE_CONNECTION_URL: url}):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()
                dsn = mock_connect.call_args.args[0]
                assert "sslmode=require" in dsn
                assert "ssl=require" not in dsn
                assert "host=HostA:5432,HostB:5432" in dsn
                assert dsn.count("host=") == 1
                assert "%3A" not in dsn
                assert "gsslib=gssapi" in dsn
                assert "krbsrvname=postgresql" in dsn
                addrs, params = _parse_asyncpg_dsn(dsn)
                assert addrs == [("HostA", 5432), ("HostB", 5432)]
                assert params.server_settings is None

    async def test_ssl_stripped_when_sslmode_already_present(self):
        """Test that ssl is stripped (not renamed) when sslmode is already
        present, to avoid server_settings pollution."""
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: "postgresql+asyncpg://user@host/db?sslmode=verify-full&ssl=require"
            }
        ):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()
                dsn = mock_connect.call_args.args[0]
                assert "sslmode=verify-full" in dsn
                assert "ssl=require" not in dsn

    async def test_ssl_renamed_preserves_unix_socket_triple_slash(self):
        """Test that renaming ssl to sslmode preserves triple-slash UNIX socket
        DSN structure (postgresql:///db) without collapsing to single slash."""
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: "postgresql+asyncpg:///mydb?host=/var/run/postgresql&ssl=require"
            }
        ):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()
                dsn = mock_connect.call_args.args[0]
                assert dsn.startswith("postgresql:///")
                assert "sslmode=require" in dsn
                assert "ssl=require" not in dsn
                assert "host=/var/run/postgresql" in dsn

    async def test_sslmode_query_param_not_modified(self):
        """Test that an existing sslmode query parameter is left untouched."""
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: "postgresql+asyncpg://user@host/db?sslmode=require"
            }
        ):
            with mock.patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                conn = await get_pg_notify_connection()

                assert conn == mock_conn
                mock_connect.assert_called_once()
                dsn = mock_connect.call_args.args[0]
                assert "sslmode=require" in dsn
