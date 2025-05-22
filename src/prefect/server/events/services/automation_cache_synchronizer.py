import asyncio
import json
from typing import Any
from uuid import UUID

import asyncpg
from typing_extensions import Literal

# Removed Awaitable, Callable as they are not directly used in this file's public API
from prefect.logging import get_logger
from prefect.server.events.models.automations import AUTOMATION_CHANGES_PG_CHANNEL
from prefect.server.events.triggers import automation_changed
from prefect.server.services.base import Service
from prefect.server.utilities.postgres_listener import (
    get_pg_notify_connection,
    pg_listen,
)
from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL, get_current_settings
from prefect.settings.models.server.services import ServicesBaseSetting

logger = get_logger(__name__)

# Copied from models.automations for type hinting, consider centralizing if used more widely
AutomationChangeEvent = Literal[
    "automation__created", "automation__updated", "automation__deleted"
]


async def _handle_automation_change_payload(payload_str: str):
    """Parses the notification payload and calls automation_changed."""
    logger.debug(f"Handling automation change payload: {payload_str}")
    try:
        payload = json.loads(payload_str)
        automation_id_str = payload.get("automation_id")
        event_type_str = payload.get("event_type")

        if not automation_id_str or not event_type_str:
            logger.error(
                f"Invalid payload on {AUTOMATION_CHANGES_PG_CHANNEL}: {payload_str}"
            )
            return

        automation_id = UUID(automation_id_str)

        literal_event_key: AutomationChangeEvent
        if event_type_str == "created":
            literal_event_key = "automation__created"
        elif event_type_str == "updated":
            literal_event_key = "automation__updated"
        elif event_type_str == "deleted":
            literal_event_key = "automation__deleted"
        else:
            logger.error(f"Unknown event_type '{event_type_str}' in notification.")
            return

        await automation_changed(automation_id, literal_event_key)
        logger.critical(
            f"Processed change for automation ID {automation_id}, event: {event_type_str}"
        )

    except json.JSONDecodeError:
        logger.error(f"JSON decode failed for payload: {payload_str}", exc_info=True)
    except Exception as e:
        logger.error(f"Error processing automation change payload: {e}", exc_info=True)


async def _run_automation_change_listener_loop(stop_event: asyncio.Event):
    """
    Main task to listen for automation changes on Postgres NOTIFY channel.
    Manages connection and invokes payload handler.
    """
    logger.critical("Automation change listener task starting.")

    while not stop_event.is_set():
        conn = None
        try:
            conn = await get_pg_notify_connection()
            if not conn:
                if stop_event.is_set():
                    break
                logger.warning(
                    f"No PG connection for {AUTOMATION_CHANGES_PG_CHANNEL}, retrying in 15s."
                )
                try:
                    # Wait for the stop_event for up to 15 seconds
                    await asyncio.wait_for(stop_event.wait(), timeout=15)
                except asyncio.TimeoutError:
                    pass  # Timeout means stop_event wasn't set, so loop again to retry connection
                continue

            logger.critical(
                f"Listener connected to Postgres for {AUTOMATION_CHANGES_PG_CHANNEL}."
            )
            async for payload in pg_listen(conn, AUTOMATION_CHANGES_PG_CHANNEL):
                if stop_event.is_set():
                    break
                await _handle_automation_change_payload(payload)

            # If pg_listen exits, it means connection likely dropped or was cancelled.
            if stop_event.is_set():
                break
            logger.info(
                f"pg_listen exited for {AUTOMATION_CHANGES_PG_CHANNEL}. Re-evaluating connection."
            )
            # Brief pause if pg_listen exits normally (e.g. connection closed by server)
            # to prevent tight reconnect loop if server is down.
            if (
                conn and not conn.is_closed()
            ):  # Should be closed by pg_listen's finally, but defensive.
                await conn.close()  # Ensure connection is closed before next attempt
            conn = None  # Ensure re-connection on next loop iteration
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass

        except (
            asyncpg.exceptions.PostgresConnectionError,
            OSError,
            ConnectionRefusedError,
        ) as e:
            logger.warning(
                f"Listener for {AUTOMATION_CHANGES_PG_CHANNEL} disconnected: {e}. Retrying in 10s."
            )
            if stop_event.is_set():
                break
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=10)
            except asyncio.TimeoutError:
                pass
        except (GeneratorExit, asyncio.CancelledError):
            logger.info("Automation change listener task cancelled.")
            break
        except Exception as e:
            logger.error(
                f"Critical error in {AUTOMATION_CHANGES_PG_CHANNEL} listener: {e}. Retrying in 30s.",
                exc_info=True,
            )
            if stop_event.is_set():
                break
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=30)
            except asyncio.TimeoutError:
                pass
        finally:
            if conn and not conn.is_closed():
                try:
                    await conn.close()
                    logger.debug(
                        f"Closed connection for {AUTOMATION_CHANGES_PG_CHANNEL} listener in main finally block."
                    )
                except Exception as e_close:
                    logger.error(
                        f"Error closing connection for {AUTOMATION_CHANGES_PG_CHANNEL} in finally: {e_close}",
                        exc_info=True,
                    )
    logger.info("Automation change listener task stopped.")


class AutomationCacheSynchronizer(Service):
    """
    A service that listens for automation changes via Postgres NOTIFY
    and updates the in-memory cache of automations.
    """

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self._listener_task: asyncio.Task[None] | None = None
        self._shutdown_event: asyncio.Event = asyncio.Event()

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        # This service has custom enablement logic in `enabled()`
        # but we can still return a base setting. For example, if we wanted
        # to add specific interval settings for it later, they'd go here.
        # For now, let's point to a general server setting or triggers if relevant.
        return get_current_settings().server.services.triggers

    @classmethod
    def enabled(cls) -> bool:
        """Enable this service only if Postgres is the configured database."""
        db_url = PREFECT_API_DATABASE_CONNECTION_URL.value()
        parent_enabled = (
            super().enabled()
        )  # Respects the setting returned by service_settings()

        is_postgres = False
        if db_url:
            try:
                # We don't need to import make_url here, just check the scheme
                is_postgres = db_url.startswith("postgresql")
            except Exception:
                logger.error(
                    "Failed to parse PREFECT_API_DATABASE_CONNECTION_URL for AutomationCacheSynchronizer enablement.",
                    exc_info=True,
                )
                is_postgres = False

        if parent_enabled and not is_postgres:
            logger.critical(
                "AutomationCacheSynchronizer will not start as the configured database is not PostgreSQL."
            )

        return parent_enabled and is_postgres

    async def start(self):
        if self._listener_task and not self._listener_task.done():
            self.logger.warning("AutomationCacheSynchronizer already started.")
            return

        self.logger.info("Starting AutomationCacheSynchronizer service.")
        self._shutdown_event.clear()
        self._listener_task = asyncio.create_task(
            _run_automation_change_listener_loop(self._shutdown_event)
        )
        self.logger.info("AutomationCacheSynchronizer service started.")
        # The Service.running() context manager will await the task.
        # This start method should just launch the task and return.

    async def stop(self):
        self.logger.info("Stopping AutomationCacheSynchronizer service.")
        if self._listener_task and not self._listener_task.done():
            self._shutdown_event.set()
            self._listener_task.cancel()  # Ensure cancellation
            try:
                await asyncio.wait_for(
                    self._listener_task, timeout=10.0
                )  # Give it time to clean up
            except asyncio.TimeoutError:
                self.logger.warning(
                    "AutomationCacheSynchronizer listener task did not stop in time."
                )
            except asyncio.CancelledError:
                self.logger.info(
                    "AutomationCacheSynchronizer listener task successfully cancelled."
                )
            except Exception as e:
                self.logger.error(
                    f"Error during listener task shutdown: {e}", exc_info=True
                )
        self._listener_task = None
        self.logger.info("AutomationCacheSynchronizer service stopped.")


# To make this service discoverable, it needs to be added to the list
# in `prefect.server.services.base._known_service_modules` or imported where
# `Service.all_services()` is called/populated.
