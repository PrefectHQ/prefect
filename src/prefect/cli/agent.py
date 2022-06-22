"""
Command line interface for working with agent services
"""
from uuid import UUID

import anyio
import typer

from prefect.agent import OrionAgent
from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli.root import app
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
    work_queue: str = typer.Argument(
        ..., help="A work queue name or ID for the agent to pull from."
    ),
    hide_welcome: bool = typer.Option(False, "--hide-welcome"),
    api: str = SettingsOption(PREFECT_API_URL),
):
    """
    Start an agent process.
    """
    try:
        work_queue_id = UUID(work_queue)
        work_queue_name = None
    except:
        work_queue_id = None
        work_queue_name = work_queue

    if not hide_welcome:
        if api:
            app.console.print(f"Starting agent connected to {api}...")
        else:
            app.console.print("Starting agent with ephemeral API...")

    async with OrionAgent(
        work_queue_id=work_queue_id,
        work_queue_name=work_queue_name,
    ) as agent:
        if not hide_welcome:
            app.console.print(ascii_name)
            app.console.print(
                f"Agent started! Looking for work from queue '{work_queue}'..."
            )

        while True:
            try:
                await agent.get_and_submit_flow_runs()
            except KeyboardInterrupt:
                break

            await anyio.sleep(PREFECT_AGENT_QUERY_INTERVAL.value())

    app.console.print("Agent stopped!")
