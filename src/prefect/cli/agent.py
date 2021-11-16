"""
Command line interface for working with agent services
"""
import typer
import anyio

from prefect import settings
from prefect.agent import OrionAgent
from prefect.cli.base import app, console
from prefect.utilities.asyncio import sync_compatible

agent_app = typer.Typer(name="agent")
app.add_typer(agent_app)


@agent_app.command()
@sync_compatible
async def start():
    """
    Start an agent service to query for and execute scheduled flow runs.
    """
    if settings.orion_host:
        console.print(f"Starting agent connected to {settings.orion_host}...")
    else:
        console.print("Starting agent with ephemeral API...")

    running = True
    async with OrionAgent() as agent:
        console.print("Agent started! Checking for flow runs...")
        while running:
            try:
                await agent.get_and_submit_flow_runs()
            except KeyboardInterrupt:
                running = False
            await anyio.sleep(settings.agent.query_interval)
    console.print("Agent stopped!")


from anyio import to_process
