import typer
import anyio
from prefect.client import OrionClient

from prefect import settings
from prefect.agents import OrionAgent
from prefect.cli.base import app, console
from prefect.utilities.asyncio import sync_compatible

agent_app = typer.Typer(name="agent")
app.add_typer(agent_app)


@agent_app.command()
@sync_compatible
async def start():
    console.print("Starting agent...")
    running = True
    async with OrionClient() as client:
        async with OrionAgent(
            prefetch_seconds=settings.orion.services.agent_prefetch_seconds,
        ) as agent:
            console.print("Agent started! Checking for flow runs...")
            while running:
                try:
                    await agent.get_and_submit_flow_runs(query_fn=client.read_flow_runs)
                except KeyboardInterrupt:
                    running = False
                await anyio.sleep(settings.orion.services.agent_loop_seconds)
    console.print("Agent stopped!")


from anyio import to_process
