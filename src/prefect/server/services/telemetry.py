"""
The Telemetry service.
"""

import logging
import os
import platform
from datetime import timedelta
from uuid import uuid4

import httpx
from docket import Depends, Perpetual

import prefect
from prefect.logging import get_logger
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.models import configuration
from prefect.server.schemas.core import Configuration
from prefect.settings import PREFECT_DEBUG_MODE
from prefect.types._datetime import now

logger: "logging.Logger" = get_logger(__name__)


async def _fetch_or_set_telemetry_session(
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> tuple[str, str]:
    """
    Fetch or create a telemetry session in the configuration table.

    Returns:
        tuple of (session_start_timestamp, session_id)
    """
    async with db.session_context(begin_transaction=True) as session:
        telemetry_session = await configuration.read_configuration(
            session, "TELEMETRY_SESSION"
        )

        if telemetry_session is None:
            logger.debug("No telemetry session found, setting")
            session_id = str(uuid4())
            session_start_timestamp = now("UTC").isoformat()

            telemetry_session = Configuration(
                key="TELEMETRY_SESSION",
                value={
                    "session_id": session_id,
                    "session_start_timestamp": session_start_timestamp,
                },
            )

            await configuration.write_configuration(session, telemetry_session)
        else:
            logger.debug("Session information retrieved from database")
            session_id: str = telemetry_session.value["session_id"]
            session_start_timestamp: str = telemetry_session.value[
                "session_start_timestamp"
            ]

    logger.debug(f"Telemetry Session: {session_id}, {session_start_timestamp}")
    return (session_start_timestamp, session_id)


async def send_telemetry_heartbeat(
    perpetual: Perpetual = Perpetual(automatic=True, every=timedelta(seconds=600)),
) -> None:
    """
    Sends anonymous telemetry data to Prefect to help us improve.

    Perpetual task that runs every 10 minutes.
    """
    from prefect.client.constants import SERVER_API_VERSION

    session_start_timestamp, session_id = await _fetch_or_set_telemetry_session()
    telemetry_environment = os.environ.get(
        "PREFECT_API_TELEMETRY_ENVIRONMENT", "production"
    )

    heartbeat = {
        "source": "prefect_server",
        "type": "heartbeat",
        "payload": {
            "platform": platform.system(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "environment": telemetry_environment,
            "ephemeral_server": bool(os.getenv("PREFECT__SERVER_EPHEMERAL", False)),
            "api_version": SERVER_API_VERSION,
            "prefect_version": prefect.__version__,
            "session_id": session_id,
            "session_start_timestamp": session_start_timestamp,
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            result = await client.post(
                "https://sens-o-matic.prefect.io/",
                json=heartbeat,
                headers={"x-prefect-event": "prefect_server"},
            )
        result.raise_for_status()
    except Exception as exc:
        logger.error(
            f"Failed to send telemetry: {exc}",
            exc_info=PREFECT_DEBUG_MODE.value(),
        )
