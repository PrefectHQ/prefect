import asyncio
from typing import (  # Added Callable, Awaitable for example
    AsyncGenerator,
    Awaitable,
    Callable,
)

import asyncpg
from sqlalchemy.engine.url import make_url  # Import for DSN parsing

from prefect.logging import get_logger
from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL

logger = get_logger(__name__)

# Define a type for the asyncpg notification callback
NotificationCallback = Callable[[asyncpg.Connection, int, str, str], Awaitable[None]]


async def get_pg_notify_connection() -> asyncpg.Connection | None:
    """
    Establishes and returns a raw asyncpg connection for LISTEN/NOTIFY.
    Returns None if not a PostgreSQL connection URL.
    """
    db_url_str = PREFECT_API_DATABASE_CONNECTION_URL.value()
    if not db_url_str:
        logger.warning(
            "Cannot create Postgres LISTEN connection: PREFECT_API_DATABASE_CONNECTION_URL is not set."
        )
        return None

    try:
        db_url = make_url(db_url_str)
    except Exception as e:
        logger.error(f"Invalid PREFECT_API_DATABASE_CONNECTION_URL: {e}")
        return None

    if db_url.drivername.split("+")[0] not in ("postgresql", "postgres"):
        logger.warning(
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
    connect_args = {
        "host": asyncpg_dsn.host,
        "port": asyncpg_dsn.port,
        "user": asyncpg_dsn.username,
        "password": asyncpg_dsn.password,
        "database": asyncpg_dsn.database,
    }
    # Filter out None values, as asyncpg.connect expects actual values or them to be absent
    filtered_connect_args = {k: v for k, v in connect_args.items() if v is not None}

    try:
        # Note: For production, connection parameters (timeouts, etc.) might need tuning.
        # This connection is outside SQLAlchemy's pool and needs its own lifecycle management.
        conn: asyncpg.Connection = await asyncpg.connect(**filtered_connect_args)
        logger.critical(
            f"Successfully established raw asyncpg connection for LISTEN/NOTIFY to "
            f"{asyncpg_dsn.host}:{asyncpg_dsn.port}/{asyncpg_dsn.database}"
        )
        return conn
    except Exception as e:
        logger.critical(
            f"Failed to establish raw asyncpg connection for LISTEN/NOTIFY: {e}",
            exc_info=True,
        )
        return None


async def pg_listen(
    connection: asyncpg.Connection, channel_name: str
) -> AsyncGenerator[str, None]:
    """
    Listens to a specific Postgres channel and yields payloads.
    Manages adding and removing the listener on the given connection.
    """
    listen_queue: asyncio.Queue[str] = asyncio.Queue()

    # asyncpg expects a regular function for the callback, not an async one directly.
    # This callback will be run in asyncpg's event loop / thread context.
    def queue_notifications_callback(
        conn_unused: asyncpg.Connection, pid: int, chan: str, payload: str
    ):
        try:
            listen_queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning(
                f"Postgres listener queue full for channel {channel_name}. Notification may be lost."
            )

    try:
        # Add the listener that uses the queue
        await connection.add_listener(channel_name, queue_notifications_callback)
        logger.critical(f"Listening on Postgres channel: {channel_name}")

        while True:
            try:
                # Wait for a notification with a timeout to allow checking if connection is still alive
                payload: str = await asyncio.wait_for(listen_queue.get(), timeout=5.0)
                yield payload
                listen_queue.task_done()  # Acknowledge processing if using Queue for tracking
            except asyncio.TimeoutError:
                if connection.is_closed():
                    logger.critical(
                        f"Postgres connection closed while listening on {channel_name}."
                    )
                    break
                continue  # Continue listening
            except (
                Exception
            ) as e:  # Catch broader exceptions during listen_queue.get() or yield
                logger.error(
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
                    logger.critical(
                        f"Connection error on {channel_name}. Listener stopping."
                    )
                    break
                await asyncio.sleep(1)  # Prevent tight loop on other continuous errors

    except (
        asyncpg.exceptions.PostgresConnectionError,
        OSError,
    ) as e:  # Errors during setup
        logger.error(
            f"Connection error setting up listener for {channel_name}: {e}",
            exc_info=True,
        )
        raise
    except (GeneratorExit, asyncio.CancelledError):  # Handle task cancellation
        logger.info(f"Listener for {channel_name} cancelled.")
        raise
    except Exception as e:  # Catch-all for unexpected errors during setup
        logger.error(
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
                logger.info(f"Removed listener from Postgres channel: {channel_name}")
            except Exception as e:
                logger.error(
                    f"Error removing listener for {channel_name}: {e}", exc_info=True
                )


# Example of how a top-level listener function using this might look (conceptual):
# async def listen_for_notifications_on_channel(channel: str, handler_coro: Callable[[str], Awaitable[None]]):
#     while True: # Outer loop for reconnection
#         conn = None
#         try:
#             conn = await get_pg_notify_connection()
#             if not conn:
#                 logger.info(f"Could not get PG connection for {channel}, retrying in 30s.")
#                 await asyncio.sleep(30)
#                 continue

#             async for payload in pg_listen(conn, channel):
#                 try:
#                     await handler_coro(payload) # Process the payload
#                 except Exception as e:
#                     logger.error(f"Error in payload handler for {channel}: {e}", exc_info=True)
#                     # Continue listening unless error is critical for the handler

#         except (asyncpg.exceptions.PostgresConnectionError, OSError, ConnectionRefusedError) as e:
#             logger.warning(f"Listener for {channel} disconnected: {e}. Reconnecting in 10s...")
#             await asyncio.sleep(10)
#         except (GeneratorExit, asyncio.CancelledError):
#             logger.info(f"Listener task for {channel} cancelled. Exiting.")
#             break
#         except Exception as e: # Catch-all for critical errors in the listener loop itself
#             logger.error(f"Critical error in listener for {channel}: {e}. Stopping. ", exc_info=True)
#             break
#         finally:
#             if conn and not conn.is_closed():
#                 try:
#                     await conn.close()
#                     logger.info(f"Closed connection for {channel} listener after attempt.")
#                 except Exception as e:
#                     logger.error(f"Error closing connection for {channel}: {e}", exc_info=True)
