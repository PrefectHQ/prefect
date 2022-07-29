"""
Command line interface for working with agent services
"""
import traceback
from collections import deque
from typing import Callable, Coroutine, Deque, List, Optional
from uuid import UUID

import anyio
import httpx
import typer

from prefect.agent import OrionAgent
from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.client import get_client
from prefect.exceptions import ObjectAlreadyExists
from prefect.settings import PREFECT_AGENT_QUERY_INTERVAL, PREFECT_API_URL
from prefect.utilities.collections import distinct

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
        help="A work queue name or ID for the agent to pull from.",
        show_default=False,
    ),
    tags: List[str] = typer.Option(
        None,
        "-t",
        "--tag",
        help="One or more optional tags that will be used to create a work queue",
    ),
    hide_welcome: bool = typer.Option(False, "--hide-welcome"),
    api: str = SettingsOption(PREFECT_API_URL),
):
    """
    Start an agent process.
    """
    if work_queue is None and not tags:
        exit_with_error(
            (
                "[red]No work queue provided![/red]\n\n"
                "Create one using `prefect work-queue create` or "
                "Pass one or more tags to `prefect agent start` and we'll create one for you!"
            ),
            style="dark_orange",
        )
    if work_queue and tags:
        exit_with_error("Only one of work_queue or tags can be provided.")
    if work_queue is not None:
        try:
            work_queue_id = UUID(work_queue)
            work_queue_name = None
        except (TypeError, ValueError):
            work_queue_id = None
            work_queue_name = work_queue
    elif tags:
        async with get_client() as client:
            try:
                work_queue_name = f"Agent queue {'-'.join(sorted(tags))}"
                work_queue_id = None
                result = await client.create_work_queue(
                    name=work_queue_name,
                    tags=tags,
                )
                app.console.print(
                    f"Created work queue '{work_queue_name}'", style="green"
                )
            except ObjectAlreadyExists:
                app.console.print(
                    f"Using work queue '{work_queue_name}'", style="green"
                )

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
        )

    app.console.print("Agent stopped!")


async def critical_service_loop(
    workload: Callable[..., Coroutine],
    interval: float,
    memory: int = 20,
):
    """
    Runs the the given `workload` function on the specified `interval`, while being
    forgiving of intermittent issues like temporary HTTP errors.  If more failures than
    successes occur, prints a summary of recently seen errors, then returns.

    Args:
        `workload`: the function to call
        `interval`: how frequently to call it
        `memory`: how many successes/failures to remember when deciding whether to exit
    """

    track_record: Deque[int] = deque(maxlen=memory)
    exceptions: Deque[Optional[Exception]] = deque(maxlen=track_record.maxlen)

    while True:
        try:
            await workload()

            track_record.append(1)
            exceptions.append(None)
        except httpx.TransportError as exc:
            # httpx.TransportError is the base class for any kind of communications
            # error, like timeouts, connection failures, etc.  This does _not_ cover
            # routine HTTP error codes (even 5xx errors like 502/503) so this
            # handler should not be attempting to cover cases where the Orion server
            # or Prefect Cloud is having an outage (which will be covered by the
            # exception clause below)
            track_record.append(-1)
            exceptions.append(exc)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (502, 503):
                # 502/503 indicate a potential outage of the Orion server or Prefect
                # Cloud, which is likely to be temporary and transient.  Don't quit
                # over these unless it is prolonged.
                track_record.append(-1)
                exceptions.append(exc)
            else:
                raise
        except KeyboardInterrupt:
            return

        # If the last result was a failure, see if it's time to cut our losses because
        # we're failing more often than we're succeeding
        if track_record[-1] < 0 and sum(track_record) < 0:
            # We've failed more than we've succeeded, the writing is on the wall.  Let's
            # explain what we've seen.
            losses = abs(sum(w for w in track_record if w < 0))
            app.console.print(
                f"\nFailed {losses} of the last {len(track_record)} attempts.  "
                "Please check your environment and configuration."
            )

            app.console.print("Examples of recent errors:\n")

            for exception in distinct(reversed(exceptions), key=lambda e: type(e)):
                if not exception:
                    continue
                app.console.print("\n".join(traceback.format_exception(exception)))
                app.console.print()
            return

        await anyio.sleep(interval)
