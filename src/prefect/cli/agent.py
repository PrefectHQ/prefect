"""
Command line interface for working with agent services
"""

import os
from functools import partial
from typing import List, Optional
from uuid import UUID

import anyio
import typer

import prefect
from prefect.agent import PrefectAgent
from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.client import get_client
from prefect.client.schemas.filters import WorkQueueFilter, WorkQueueFilterName
from prefect.exceptions import ObjectNotFound
from prefect.settings import (
    PREFECT_AGENT_PREFETCH_SECONDS,
    PREFECT_AGENT_QUERY_INTERVAL,
    PREFECT_API_URL,
)
from prefect.utilities.processutils import setup_signal_handlers_agent
from prefect.utilities.services import critical_service_loop

agent_app = PrefectTyper(
    name="agent",
    help="Commands for starting and interacting with agent processes.",
    deprecated=True,
    deprecated_name="agent",
    deprecated_start_date="Mar 2024",
    deprecated_help="Use `prefect worker start` instead. Refer to the upgrade guide for more information: https://docs.prefect.io/latest/guides/upgrade-guide-agents-to-workers/. ",
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
    work_queue_prefix: List[str] = typer.Option(
        None,
        "-m",
        "--match",
        help=(
            "Dynamically matches work queue names with the specified prefix for the"
            " agent to pull from,for example `dev-` will match all work queues with a"
            " name that starts with `dev-`"
        ),
    ),
    work_pool_name: str = typer.Option(
        None,
        "-p",
        "--pool",
        help="A work pool name for the agent to pull from.",
    ),
    hide_welcome: bool = typer.Option(False, "--hide-welcome"),
    api: str = SettingsOption(PREFECT_API_URL),
    run_once: bool = typer.Option(
        False, help="Run the agent loop once, instead of forever."
    ),
    prefetch_seconds: int = SettingsOption(PREFECT_AGENT_PREFETCH_SECONDS),
    # deprecated tags
    tags: List[str] = typer.Option(
        None,
        "-t",
        "--tag",
        help=(
            "DEPRECATED: One or more optional tags that will be used to create a work"
            " queue. This option will be removed on 2023-02-23."
        ),
    ),
    limit: int = typer.Option(
        None,
        "-l",
        "--limit",
        help="Maximum number of flow runs to start simultaneously.",
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
            (
                "Agents now support multiple work queues. Instead of passing a single"
                " argument, provide work queue names with the `-q` or `--work-queue`"
                f" flag: `prefect agent start -q {work_queue}`\n"
            ),
            style="blue",
        )
    if work_pool_name:
        is_queues_paused = await _check_work_queues_paused(
            work_pool_name=work_pool_name,
            work_queues=work_queues,
        )
        if is_queues_paused:
            queue_scope = (
                "The 'default' work queue"
                if not work_queues
                else "Specified work queue(s)"
            )
            app.console.print(
                (
                    f"{queue_scope} in the work pool {work_pool_name!r} is currently"
                    " paused. This agent will not execute any flow runs until the work"
                    " queue(s) are unpaused."
                ),
                style="yellow",
            )

    if not work_queues and not tags and not work_queue_prefix and not work_pool_name:
        exit_with_error("No work queues provided!", style="red")
    elif bool(work_queues) + bool(tags) + bool(work_queue_prefix) > 1:
        exit_with_error(
            "Only one of `work_queues`, `match`, or `tags` can be provided.",
            style="red",
        )
    if work_pool_name and tags:
        exit_with_error(
            "`tag` and `pool` options cannot be used together.", style="red"
        )

    if tags:
        work_queue_name = f"Agent queue {'-'.join(sorted(tags))}"
        app.console.print(
            (
                "`tags` are deprecated. For backwards-compatibility with old versions"
                " of Prefect, this agent will create a work queue named"
                f" `{work_queue_name}` that uses legacy tag-based matching. This option"
                " will be removed on 2023-02-23."
            ),
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

    agent_process_id = os.getpid()
    setup_signal_handlers_agent(
        agent_process_id, "the Prefect agent", app.console.print
    )

    async with PrefectAgent(
        work_queues=work_queues,
        work_queue_prefix=work_queue_prefix,
        work_pool_name=work_pool_name,
        prefetch_seconds=prefetch_seconds,
        limit=limit,
    ) as agent:
        if not hide_welcome:
            app.console.print(ascii_name)
            if work_pool_name:
                app.console.print(
                    "Agent started! Looking for work from "
                    f"work pool '{work_pool_name}'..."
                )
            elif work_queue_prefix:
                app.console.print(
                    "Agent started! Looking for work from "
                    f"queue(s) that start with the prefix: {work_queue_prefix}..."
                )
            else:
                app.console.print(
                    "Agent started! Looking for work from "
                    f"queue(s): {', '.join(work_queues)}..."
                )

        async with anyio.create_task_group() as tg:
            tg.start_soon(
                partial(
                    critical_service_loop,
                    agent.get_and_submit_flow_runs,
                    PREFECT_AGENT_QUERY_INTERVAL.value(),
                    printer=app.console.print,
                    run_once=run_once,
                    jitter_range=0.3,
                    backoff=4,  # Up to ~1 minute interval during backoff
                )
            )

            tg.start_soon(
                partial(
                    critical_service_loop,
                    agent.check_for_cancelled_flow_runs,
                    PREFECT_AGENT_QUERY_INTERVAL.value() * 2,
                    printer=app.console.print,
                    run_once=run_once,
                    jitter_range=0.3,
                    backoff=4,
                )
            )

    app.console.print("Agent stopped!")


async def _check_work_queues_paused(
    work_pool_name: str, work_queues: Optional[List[str]]
) -> bool:
    """
    Check if the default work queue in the work pool is paused. If work queues are specified,
    only those work queues are checked.

    Args:
        - work_pool_name (str): the name of the work pool to check
        - work_queues (Optional[List[str]]): the names of the work queues to check

    Returns:
        - bool: True if work queues are paused, False otherwise
    """
    work_queues_list = work_queues or ["default"]
    try:
        work_queues_filter = WorkQueueFilter(
            name=WorkQueueFilterName(any_=work_queues_list)
        )
        async with get_client() as client:
            wqs = await client.read_work_queues(
                work_pool_name=work_pool_name, work_queue_filter=work_queues_filter
            )
            return all(queue.is_paused for queue in wqs) if wqs else False
    except ObjectNotFound:
        return False
