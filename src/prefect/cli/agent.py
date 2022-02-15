"""
Command line interface for working with agent services
"""
import anyio
import typer

from prefect.agent import OrionAgent
from prefect.cli.base import PrefectTyper, SettingsOption, app, console
from prefect.settings import PREFECT_AGENT_QUERY_INTERVAL, PREFECT_API_URL

agent_app = PrefectTyper(
    name="agent", help="Commands for starting and interacting with agent processes."
)
app.add_typer(agent_app)


ascii_name = r"""
  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____ 
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |  
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_| 

"""


@agent_app.command()
async def start(
    hide_welcome: bool = typer.Option(False, "--hide-welcome"),
    api: str = SettingsOption(PREFECT_API_URL),
):
    """
    Start an agent process.
    """
    if not hide_welcome:
        if api:
            console.print(f"Starting agent connected to {api}...")
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
            await anyio.sleep(PREFECT_AGENT_QUERY_INTERVAL.get())

    console.print("Agent stopped!")
