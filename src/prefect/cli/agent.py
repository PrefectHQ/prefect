"""
Command line interface for working with agent services
"""
from typing import List
from uuid import UUID

import typer

import prefect
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
    # deprecated main argument
    work_queue: str = typer.Argument(
        None,
        show_default=False,
        help="DEPRECATED: A work queue name or ID",
    ),
    work_queues: List[str] = typer.Option(
        None,
        "-q",
        "--work-queue",
        help="One or more work queue names for the agent to pull from.",
    ),
    work_queue_prefix: str = typer.Option(
        None,
        "-m",
        "--match",
        help=(
            "Dynamically matches work queue names with the specified prefix for the agent to pull from,"
            "for example `dev-` will match all work queues with a name that starts with `dev-`"
        ),
    ),
    hide_welcome: bool = typer.Option(False, "--hide-welcome"),
    api: str = SettingsOption(PREFECT_API_URL),
    # deprecated tags
    tags: List[str] = typer.Option(
        None,
        "-t",
        "--tag",
        help="DEPRECATED: One or more optional tags that will be used to create a work queue",
    ),
):
    """
    Start an agent process to poll one or more work queues for flow runs.
    """
    work_queues = work_queues or []

    if work_queue is not None:
        # try to treat the work_queue as a UUID
        try:
            async with get_client() as client:
                q = await client.read_work_queue(UUID(work_queue))
                work_queue = q.name
        # otherwise treat it as a string name
        except (TypeError, ValueError):
            pass
        work_queues.append(work_queue)
        app.console.print(
            "Agents now support multiple work queues. Instead of passing a single argument, provide work queue names "
            f"with the `-q` or `--work-queue` flag: `prefect agent start -q {work_queue}`\n",
            style="blue",
        )

    if not work_queues and not tags and not work_queue_prefix:
        exit_with_error("No work queues provided!", style="red")
    elif bool(work_queues) + bool(tags) + bool(work_queue_prefix) > 1:
        exit_with_error(
            "Only one of `work_queues`, `match`, or `tags` can be provided.",
            style="red",
        )

    if tags:
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

        work_queues = [work_queue_name]

    if not hide_welcome:
        if api:
            app.console.print(
                f"Starting v{prefect.__version__} agent connected to {api}..."
            )
        else:
            app.console.print(
                f"Starting v{prefect.__version__} agent with ephemeral API..."
            )

    async with OrionAgent(
        work_queues=work_queues, work_queue_prefix=work_queue_prefix
    ) as agent:
        if not hide_welcome:
            app.console.print(ascii_name)
            if work_queue_prefix:
                app.console.print(
                    "Agent started! Looking for work from "
                    f"queue(s) that start with the prefix: {work_queue_prefix}..."
                )
            else:
                app.console.print(
                    "Agent started! Looking for work from "
                    f"queue(s): {', '.join(work_queues)}..."
                )

        await critical_service_loop(
            agent.get_and_submit_flow_runs,
            PREFECT_AGENT_QUERY_INTERVAL.value(),
            printer=app.console.print,
        )

    app.console.print("Agent stopped!")
