"""
The LightLoopService service. Responsible for running all services that don't require dedicated threads or resources.
"""

import asyncio
from logging import Logger
from typing import Callable, List
from uuid import uuid4

import httpx
import pendulum

import prefect
from prefect.logging import get_logger
from prefect.orion.services.loop_service import LoopService
from prefect.settings import PREFECT_ORION_TELEMETRY_ENABLED


class LightLoopService(LoopService):
    """
    This service is meant to hold low-resource functionality that needs to happen on a recurring basis. For example, in Kubernetes setups, each Prefect service may recieve its own pod. For some processess, that's simply heavy and wasteful. This service intends to encapsulate all of those routines that don't require this.
    """

    def __init__(self) -> None:
        super().__init__()
        self.logger.debug(f"LightLoopService started")

        # Initialize values for the service to manage itself
        self.functions_to_call: List[Callable] = []

        # Initialize values for telemetry if enabled
        if PREFECT_ORION_TELEMETRY_ENABLED.value():
            self.telemetry_session_id: str = str(uuid4())
            self.telemetry_session_start_timestamp: str = (
                pendulum.now().to_iso8601_string()
            )
            self.functions_to_call.append(self._run_telemetry)

    async def run_once(self) -> None:
        if not self.functions_to_call:
            self.stop()

        for function in self.functions_to_call:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(function())
            # if an error is raised, log and continue
            except Exception as exc:
                self.logger.exception(f"Unexpected error in: {repr(exc)}")

    async def _run_telemetry(self):
        """
        Sends a heartbeat to the sens-o-matic
        """
        # run every ten minutes
        if not pendulum.now().minute % 10 != 0:
            return

        from prefect.orion.api.server import ORION_API_VERSION

        async with httpx.AsyncClient() as client:
            result = await client.post(
                "https://sens-o-matic.prefect.io/",
                json={
                    "source": "prefect_server",
                    "type": "orion_heartbeat",
                    "payload": {
                        "environment": "production",
                        "api_version": ORION_API_VERSION,
                        "prefect_version": prefect.__version__,
                        "session_id": self.telemetry_session_id,
                        "session_start_timestamp": self.telemetry_session_start_timestamp,
                    },
                },
                headers={
                    "x-prefect-event": "prefect_server",
                },
            )
            self.logger.debug(f"Telemetry request result: {result.json()}")


if __name__ == "__main__":
    asyncio.run(LightLoopService().start())
