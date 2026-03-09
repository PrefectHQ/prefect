from __future__ import annotations

import asyncio
import ssl
from typing import TYPE_CHECKING, Any, AsyncGenerator
from urllib.parse import urlsplit, urlunsplit

import asyncpg  # type: ignore
from pydantic import SecretStr
from sqlalchemy.engine.url import make_url

if TYPE_CHECKING:
    from asyncpg import Connection

from prefect.logging import get_logger
from prefect.settings import get_current_settings

_logger = get_logger(__name__)


async def get_pg_notify_connection() -> Connection | None:
    """
    Establishes and returns a raw asyncpg connection for LISTEN/NOTIFY.
    Returns None if not a PostgreSQL connection URL.
    """
    db_url_str = get_current_settings().server.database.connection_url
    if isinstance(db_url_str, SecretStr):
        db_url_str = db_url_str.get_secret_value()

    if not db_url_str:
        _logger.debug(
            "Cannot create Postgres LISTEN connection: PREFECT_API_DATABASE_CONNECTION_URL is not set."
        )
        return None

    try:
        db_url = make_url(db_url_str)
    except Exception as e:
        _logger.error(f"Invalid PREFECT_API_DATABASE_CONNECTION_URL: {e}")
        return None

    if db_url.drivername.split("+")[0] not in ("postgresql", "postgres"):
        _logger.debug(
            "Cannot create Postgres LISTEN connection: PREFECT_API_DATABASE_CONNECTION_URL "
            f"is not a PostgreSQL connection URL (driver: {db_url.drivername})."
        )
        return None

    # Construct a DSN for asyncpg by stripping the SQLAlchemy dialect suffix
    # (e.g. +asyncpg) via simple string replacement on the scheme portion. This
    # preserves the original URL structure exactly, including:
    #   - multihost connection strings (?host=A:5432&host=B:5432)
    #   - Kerberos/GSSAPI params (krbsrvname, gsslib)
    #   - UNIX domain socket paths (triple-slash URLs like postgresql:///db)
    # We intentionally avoid SQLAlchemy's render_as_string() here because it
    # URL-encodes query param values (e.g. ':' -> '%3A'), which breaks asyncpg's
    # parsing of host:port pairs in multihost configurations.
    original_scheme = urlsplit(db_url_str).scheme  # e.g. "postgresql+asyncpg"
    base_scheme = original_scheme.split("+")[0]  # e.g. "postgresql"
    dsn_string = base_scheme + db_url_str[len(original_scheme) :]

    # Rename the non-standard 'ssl' query parameter to 'sslmode' so asyncpg
    # recognises it as a connection parameter instead of passing it through as
    # a PostgreSQL server setting (which causes CantChangeRuntimeParamError).
    # asyncpg's DSN parser handles 'sslmode' but not 'ssl'; the bare 'ssl'
    # key is only accepted as a keyword argument to asyncpg.connect().
    # We manipulate the raw query string directly (rather than parse_qs +
    # urlencode) to avoid re-encoding values such as colons in multihost
    # host:port pairs, which would break asyncpg's parsing.
    split = urlsplit(dsn_string)
    if split.query:
        raw_params = split.query.split("&")
        param_keys = [p.split("=", 1)[0] for p in raw_params]
        if "ssl" in param_keys and "sslmode" not in param_keys:
            # Rename ssl → sslmode, preserving all raw values exactly
            new_params = [
                "sslmode" + p[3:] if p.split("=", 1)[0] == "ssl" else p
                for p in raw_params
            ]
            dsn_string = urlunsplit(
                (
                    split.scheme,
                    split.netloc,
                    split.path,
                    "&".join(new_params),
                    split.fragment,
                )
            )
        elif "ssl" in param_keys and "sslmode" in param_keys:
            # sslmode already present; strip ssl to avoid server_settings pollution
            new_params = [p for p in raw_params if p.split("=", 1)[0] != "ssl"]
            dsn_string = urlunsplit(
                (
                    split.scheme,
                    split.netloc,
                    split.path,
                    "&".join(new_params),
                    split.fragment,
                )
            )

    connect_args: dict[str, Any] = {}

    # Include server_settings if configured
    settings = get_current_settings()
    server_settings: dict[str, str] = {}
    app_name = settings.server.database.sqlalchemy.connect_args.application_name
    if app_name:
        server_settings["application_name"] = app_name
    search_path = settings.server.database.sqlalchemy.connect_args.search_path
    if search_path:
        server_settings["search_path"] = search_path
    if server_settings:
        connect_args["server_settings"] = server_settings

    try:
        # Include TLS/SSL configuration if enabled, mirroring the main engine setup
        # in AsyncPostgresConfiguration.engine(). This is inside the try block so
        # that TLS misconfigurations (e.g. invalid cert paths) are caught and result
        # in returning None, consistent with this function's fault-tolerant contract.
        tls_config = settings.server.database.sqlalchemy.connect_args.tls
        if tls_config.enabled:
            if tls_config.ca_file:
                pg_ctx = ssl.create_default_context(
                    purpose=ssl.Purpose.SERVER_AUTH, cafile=tls_config.ca_file
                )
            else:
                pg_ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)

            pg_ctx.minimum_version = ssl.TLSVersion.TLSv1_2

            if tls_config.cert_file and tls_config.key_file:
                pg_ctx.load_cert_chain(
                    certfile=tls_config.cert_file, keyfile=tls_config.key_file
                )

            pg_ctx.check_hostname = tls_config.check_hostname
            pg_ctx.verify_mode = ssl.CERT_REQUIRED
            connect_args["ssl"] = pg_ctx

        # Pass the full DSN to asyncpg so it can parse all connection parameters
        # natively, including authentication-related query params (e.g. krbsrvname
        # for Kerberos/GSSAPI) and UNIX domain socket paths.
        # This connection is outside SQLAlchemy's pool and needs its own lifecycle
        # management.
        conn = await asyncpg.connect(dsn_string, **connect_args)
        _logger.info(
            f"Successfully established raw asyncpg connection for LISTEN/NOTIFY to "
            f"{db_url.host or db_url.query.get('host', 'localhost')}/"
            f"{db_url.database}"
        )
        return conn
    except Exception as e:
        _logger.error(
            f"Failed to establish raw asyncpg connection for LISTEN/NOTIFY: {e}",
            exc_info=True,
        )
        return None


async def pg_listen(
    connection: Connection, channel_name: str, heartbeat_interval: float = 5.0
) -> AsyncGenerator[str, None]:
    """
    Listens to a specific Postgres channel and yields payloads.
    Manages adding and removing the listener on the given connection.
    """
    listen_queue: asyncio.Queue[str] = asyncio.Queue()

    # asyncpg expects a regular function for the callback, not an async one directly.
    # This callback will be run in asyncpg's event loop / thread context.
    def queue_notifications_callback(
        conn_unused: Connection, pid: int, chan: str, payload: str
    ):
        try:
            listen_queue.put_nowait(payload)
        except asyncio.QueueFull:
            _logger.warning(
                f"Postgres listener queue full for channel {channel_name}. Notification may be lost."
            )

    try:
        # Add the listener that uses the queue
        await connection.add_listener(channel_name, queue_notifications_callback)
        _logger.info(f"Listening on Postgres channel: {channel_name}")

        while True:
            try:
                # Wait for a notification with a timeout to allow checking if connection is still alive
                payload: str = await asyncio.wait_for(
                    listen_queue.get(), timeout=heartbeat_interval
                )
                yield payload
                listen_queue.task_done()  # Acknowledge processing if using Queue for tracking
            except asyncio.TimeoutError:
                if connection.is_closed():
                    _logger.info(
                        f"Postgres connection closed while listening on {channel_name}."
                    )
                    break
                continue  # Continue listening
            except (
                Exception
            ) as e:  # Catch broader exceptions during listen_queue.get() or yield
                _logger.error(
                    f"Error during notification processing on {channel_name}: {e}",
                    exc_info=True,
                )
                # Depending on the error, you might want to break or continue
                if isinstance(
                    e, (GeneratorExit, asyncio.CancelledError)
                ):  # Graceful shutdown
                    raise
                if isinstance(
                    e, (asyncpg.exceptions.PostgresConnectionError, OSError)
                ):  # Connection critical
                    _logger.error(
                        f"Connection error on {channel_name}. Listener stopping."
                    )
                    break
                await asyncio.sleep(1)  # Prevent tight loop on other continuous errors

    except (
        asyncpg.exceptions.PostgresConnectionError,
        OSError,
    ) as e:  # Errors during setup
        _logger.error(
            f"Connection error setting up listener for {channel_name}: {e}",
            exc_info=True,
        )
        raise
    except (GeneratorExit, asyncio.CancelledError):  # Handle task cancellation
        _logger.info(f"Listener for {channel_name} cancelled.")
        raise
    except Exception as e:  # Catch-all for unexpected errors during setup
        _logger.error(
            f"Unexpected error setting up or during listen on {channel_name}: {e}",
            exc_info=True,
        )
        raise
    finally:
        if not connection.is_closed():
            try:
                await connection.remove_listener(
                    channel_name, queue_notifications_callback
                )
                _logger.info(f"Removed listener from Postgres channel: {channel_name}")
            except Exception as e:
                _logger.error(
                    f"Error removing listener for {channel_name}: {e}", exc_info=True
                )
