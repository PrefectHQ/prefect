import asyncio
import sys
from functools import partial
from typing import Optional

import prefect
from prefect.agents import OrionAgent
from prefect.orion.models.flow_runs import read_flow_runs
from prefect.orion.services.loop_service import LoopService

settings = prefect.settings.orion.services


class Agent(LoopService):
    loop_seconds: float = settings.agent_loop_seconds

    def __init__(self, loop_seconds: float = settings.agent_loop_seconds):
        super().__init__(loop_seconds=loop_seconds)
        self.agent: Optional[OrionAgent] = None

    async def run_once(self) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                await self.agent.get_and_submit_flow_runs(
                    query_fn=partial(read_flow_runs, session)
                )

    async def setup(self) -> None:
        await super().setup()
        self.agent = OrionAgent(prefetch_seconds=settings.agent_prefetch_seconds)
        await self.agent.start()

    async def shutdown(self) -> None:
        await super().shutdown()
        # Exception info is important for a clean teardown of agent work
        await self.agent.shutdown(*sys.exc_info())
        self.agent = None


if __name__ == "__main__":
    asyncio.run(Agent().start())
