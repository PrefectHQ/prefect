from concurrent.futures.process import ProcessPoolExecutor
import typer
import anyio
from prefect.client import OrionClient

from prefect.agent import Agent
from prefect.cli.base import app, console
from prefect.utilities.asyncio import sync_compatible
from functools import partial

agent_app = typer.Typer(name="agent")
app.add_typer(agent_app)


@agent_app.command()
@sync_compatible
async def start(max_workers: int = None):
    console.print("Starting agent...")
    running = True
    async with OrionClient() as client:
        async with Agent(
            prefetch_seconds=10,
            query_fn=client.read_flow_runs,
        ) as agent:
            console.print("Agent started! Checking for flow runs...")
            while running:
                try:
                    await agent.get_and_submit_flow_runs()
                except KeyboardInterrupt:
                    running = False
                await anyio.sleep(2)
    console.print("Agent stopped!")


from anyio import to_process
