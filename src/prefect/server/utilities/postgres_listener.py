from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, AsyncGenerator

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

    # Construct a new DSN for asyncpg, omitting the dialect part like '+asyncpg'
    # and ensuring essential components are present.
    asyncpg_dsn = db_url.set(
        drivername="postgresql"
    )  # Ensure drivername is plain postgresql

    # asyncpg.connect can take individual params or a DSN string.
    # We'll pass params directly from the parsed URL if they exist to be explicit.
    # Build connection arguments, ensuring proper types
    connect_args = {}
    if asyncpg_dsn.host:
        connect_args["host"] = asyncpg_dsn.host
    if asyncpg_dsn.port:
        connect_args["port"] = asyncpg_dsn.port
    if asyncpg_dsn.username:
        connect_args["user"] = asyncpg_dsn.username
    if asyncpg_dsn.password:
        connect_args["password"] = asyncpg_dsn.password
    if asyncpg_dsn.database:
        connect_args["database"] = asyncpg_dsn.database

    try:
        # Note: For production, connection parameters (timeouts, etc.) might need tuning.
        # This connection is outside SQLAlchemy's pool and needs its own lifecycle management.
        conn = await asyncpg.connect(**connect_args)
        _logger.info(
            f"Successfully established raw asyncpg connection for LISTEN/NOTIFY to "
            f"{asyncpg_dsn.host}:{asyncpg_dsn.port}/{asyncpg_dsn.database}"
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
