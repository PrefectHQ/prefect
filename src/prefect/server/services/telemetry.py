"""
The Telemetry service.
"""

import asyncio
import os
import platform
from typing import Any, Optional
from uuid import uuid4

import httpx

import prefect
import prefect.settings
from prefect.server.database import PrefectDBInterface
from prefect.server.database.dependencies import db_injector
from prefect.server.models import configuration
from prefect.server.schemas.core import Configuration
from prefect.server.services.base import LoopService
from prefect.settings import PREFECT_DEBUG_MODE
from prefect.settings.context import get_current_settings
from prefect.settings.models.server.services import ServicesBaseSetting
from prefect.types._datetime import now


class Telemetry(LoopService):
    """
    Sends anonymous data to Prefect to help us improve

    It can be toggled off with the PREFECT_SERVER_ANALYTICS_ENABLED setting.
    """

    loop_seconds: float = 600

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        raise NotImplementedError("Telemetry service does not have settings")

    @classmethod
    def environment_variable_name(cls) -> str:
        return "PREFECT_SERVER_ANALYTICS_ENABLED"

    @classmethod
    def enabled(cls) -> bool:
        return get_current_settings().server.analytics_enabled

    def __init__(self, loop_seconds: Optional[int] = None, **kwargs: Any):
        super().__init__(loop_seconds=loop_seconds, **kwargs)
        self.telemetry_environment: str = os.environ.get(
            "PREFECT_API_TELEMETRY_ENVIRONMENT", "production"
        )

    @db_injector
    async def _fetch_or_set_telemetry_session(self, db: PrefectDBInterface):
        """
        This method looks for a telemetry session in the configuration table. If there
        isn't one, it sets one. It then sets `self.session_id` and
        `self.session_start_timestamp`.

        Telemetry sessions last until the database is reset.
        """
        async with db.session_context(begin_transaction=True) as session:
            telemetry_session = await configuration.read_configuration(
                session, "TELEMETRY_SESSION"
            )

            if telemetry_session is None:
                self.logger.debug("No telemetry session found, setting")
                session_id = str(uuid4())
                session_start_timestamp = now("UTC").to_iso8601_string()

                telemetry_session = Configuration(
                    key="TELEMETRY_SESSION",
                    value={
                        "session_id": session_id,
                        "session_start_timestamp": session_start_timestamp,
                    },
                )

                await configuration.write_configuration(session, telemetry_session)

                self.session_id = session_id
                self.session_start_timestamp = session_start_timestamp
            else:
                self.logger.debug("Session information retrieved from database")
                self.session_id: str = telemetry_session.value["session_id"]
                self.session_start_timestamp: str = telemetry_session.value[
                    "session_start_timestamp"
                ]
        self.logger.debug(
            f"Telemetry Session: {self.session_id}, {self.session_start_timestamp}"
        )
        return (self.session_start_timestamp, self.session_id)

    async def run_once(self) -> None:
        """
        Sends a heartbeat to the sens-o-matic
        """
        from prefect.client.constants import SERVER_API_VERSION

        if not hasattr(self, "session_id"):
            await self._fetch_or_set_telemetry_session()

        heartbeat = {
            "source": "prefect_server",
            "type": "heartbeat",
            "payload": {
                "platform": platform.system(),
                "architecture": platform.machine(),
                "python_version": platform.python_version(),
                "python_implementation": platform.python_implementation(),
                "environment": self.telemetry_environment,
                "ephemeral_server": bool(os.getenv("PREFECT__SERVER_EPHEMERAL", False)),
                "api_version": SERVER_API_VERSION,
                "prefect_version": prefect.__version__,
                "session_id": self.session_id,
                "session_start_timestamp": self.session_start_timestamp,
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
            self.logger.error(
                f"Failed to send telemetry: {exc}\nShutting down telemetry service...",
                # The traceback is only needed if doing deeper debugging, otherwise
                # this looks like an impactful server error
                exc_info=PREFECT_DEBUG_MODE.value(),
            )
            await self.stop(block=False)


if __name__ == "__main__":
    asyncio.run(Telemetry(handle_signals=True).start())
