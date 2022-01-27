"""
Command line interface for working with agent services
"""
import typer
import anyio

from prefect import settings
from prefect.agent import OrionAgent
from prefect.cli.base import app, console
from prefect.utilities.asyncio import sync_compatible

agent_app = typer.Typer(
    name="agent", help="Commands for starting and interacting with agent processes."
)
app.add_typer(agent_app)


ascii_name = r"""
 ____            __           _        _                    _
|  _ \ _ __ ___ / _| ___  ___| |_     / \   __ _  ___ _ __ | |_
| |_) | '__/ _ \ |_ / _ \/ __| __|   / _ \ / _` |/ _ \ '_ \| __|
|  __/| | |  __/  _|  __/ (__| |_   / ___ \ (_| |  __/ | | | |_
|_|   |_|  \___|_|  \___|\___|\__| /_/   \_\__, |\___|_| |_|\__|
                                           |___/
"""


@agent_app.command()
@sync_compatible
async def start(host=settings.orion_host):
    """
    Start an agent process.
    """
    if host:
        console.print(f"Starting agent connected to {host}...")
    else:
        console.print("Starting agent with ephemeral API...")

    running = True
    async with OrionAgent() as agent:
        console.print(ascii_name)
        console.print("Agent started! Checking for flow runs...")
        while running:
            try:
                await agent.get_and_submit_flow_runs()
            except KeyboardInterrupt:
                running = False
            await anyio.sleep(settings.agent.query_interval)
    console.print("Agent stopped!")
