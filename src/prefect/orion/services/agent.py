import asyncio

import pendulum
import sqlalchemy as sa

import prefect
from prefect.orion import models
from prefect.orion.services.loop_service import LoopService
from prefect.utilities.collections import batched_iterable

settings = prefect.settings.orion.services


class Agent(LoopService):
    loop_seconds: float = settings.agent_loop_seconds

    async def run_once(self):
        pass


if __name__ == "__main__":
    asyncio.run(Agent().start())
