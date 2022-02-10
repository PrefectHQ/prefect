"""
Command line interface for working with agent services
"""
import anyio
import typer

import prefect.settings
from prefect.agent import OrionAgent
from prefect.cli.base import app, console
from prefect.utilities.asyncio import sync_compatible

agent_app = typer.Typer(
    name="agent", help="Commands for starting and interacting with agent processes."
)
app.add_typer(agent_app)


ascii_name = """
  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____ 
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |  
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_| 

"""


@agent_app.command()
@sync_compatible
async def start(
    hide_welcome: bool = typer.Option(False, "--hide-welcome"),
    host: str = prefect.settings.from_env().orion_host,
):
    """
    Start an agent process.
    """
    if not hide_welcome:
        if prefect.settings.from_env().orion_host:
            console.print(f"Starting agent connected to {host}...")
        else:
            console.print("Starting agent with ephemeral API...")

    running = True
    async with OrionAgent() as agent:
        if not hide_welcome:
            console.print(ascii_name)
            console.print("Agent started!")
        while running:
            try:
                await agent.get_and_submit_flow_runs()
            except KeyboardInterrupt:
                running = False
            await anyio.sleep(prefect.settings.from_env().agent.query_interval)

    console.print("Agent stopped!")
