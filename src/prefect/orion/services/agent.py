"""
The Agent service. Responsible for executing scheduled flow runs from deployments.

The Agent service queries for flows scheduled to start now or in the very near future.
How far forward the Agent will "prefecth" these flows can be configured by changing
prefect.settings.orion.services.agent_prefetch_seconds).

To execute flow runs, the Agent service submits them to a subprocess. The environment
must be compatible with Orion to execute these subprocesses.
"""

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
    """
    A simple loop service for executing scheduled flow runs.
    """

    loop_seconds: float = settings.agent_loop_seconds

    def __init__(self, loop_seconds: float = settings.agent_loop_seconds):
        super().__init__(loop_seconds=loop_seconds)
        self.agent: Optional[OrionAgent] = None

    async def run_once(self) -> None:
        """
        Query for any flow runs scheduled to start and execute them.
        """
        async with self.session_factory() as session:
            async with session.begin():
                await self.agent.get_and_submit_flow_runs(
                    query_fn=partial(read_flow_runs, session)
                )

    async def setup(self) -> None:
        """Setup the agent service."""
        await super().setup()
        self.agent = OrionAgent(prefetch_seconds=settings.agent_prefetch_seconds)
        await self.agent.start()

    async def shutdown(self) -> None:
        """Shut down the agent service."""
        await super().shutdown()
        # Exception info is important for a clean teardown of agent work
        await self.agent.shutdown(*sys.exc_info())
        self.agent = None


if __name__ == "__main__":
    asyncio.run(Agent().start())
