"""
Command line interface for working with agent services
"""
from typing import List
from uuid import UUID

import typer

from prefect.agent import OrionAgent
from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.client import get_client
from prefect.exceptions import ObjectNotFound
from prefect.settings import PREFECT_AGENT_QUERY_INTERVAL, PREFECT_API_URL
from prefect.utilities.services import critical_service_loop

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
        None,
        show_default=False,
    ),
    tags: List[str] = typer.Option(
        None,
        "-t",
        "--tag",
        help="DEPRECATED: One or more optional tags that will be used to create a work queue",
    ),
    hide_welcome: bool = typer.Option(False, "--hide-welcome"),
    api: str = SettingsOption(PREFECT_API_URL),
):
    """
    Start an agent process.
    """

    if work_queue is None and not tags:
        exit_with_error("No work queue provided!", style="red")
    elif work_queue and tags:
        exit_with_error("Only one of `work_queue` or `tags` can be provided.")

    if work_queue is not None:
        try:
            work_queue_id = UUID(work_queue)
            work_queue_name = None
        except (TypeError, ValueError):
            work_queue_id = None
            work_queue_name = work_queue
    elif tags:
        work_queue_name = f"Agent queue {'-'.join(sorted(tags))}"
        app.console.print(
            "`tags` are deprecated. For backwards-compatibility with old "
            f"versions of Prefect, this agent will create a work queue named `{work_queue_name}` "
            "that uses legacy tag-based matching.",
            style="red",
        )

        async with get_client() as client:
            try:
                work_queue = await client.read_work_queue_by_name(work_queue_name)
                if work_queue.filter is None:
                    # ensure the work queue has legacy (deprecated) tag-based behavior
                    await client.update_work_queue(filter=dict(tags=tags))
            except ObjectNotFound:
                # if the work queue doesn't already exist, we create it with tags
                # to enable legacy (deprecated) tag-matching behavior
                await client.create_work_queue(name=work_queue_name, tags=tags)

        work_queue_id = None

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
                "Agent started! Looking for work from "
                f"queue '{work_queue_name or work_queue_id}'..."
            )

        await critical_service_loop(
            agent.get_and_submit_flow_runs,
            PREFECT_AGENT_QUERY_INTERVAL.value(),
            printer=app.console.print,
        )

    app.console.print("Agent stopped!")
