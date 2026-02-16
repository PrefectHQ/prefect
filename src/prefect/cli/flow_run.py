"""
Command line interface for working with flow runs
"""

from __future__ import annotations

import logging
import os
import signal
import threading
import webbrowser
from types import FrameType
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from prefect.utilities.callables import get_call_parameters, parameters_to_args_kwargs

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import FlowRun

import httpx
import orjson
import typer
from rich.markup import escape
from rich.pretty import Pretty
from rich.table import Table
from starlette import status

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app, is_interactive
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import FlowFilter, FlowRunFilter, LogFilter
from prefect.client.schemas.objects import StateType
from prefect.client.schemas.responses import SetStateStatus
from prefect.client.schemas.sorting import FlowRunSort, LogSort
from prefect.exceptions import ObjectNotFound
from prefect.logging import get_logger
from prefect.runner import Runner
from prefect.states import State, exception_to_crashed_state
from prefect.types._datetime import human_friendly_diff
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.urls import url_for

flow_run_app: PrefectTyper = PrefectTyper(
    name="flow-run", help="Interact with flow runs."
)
app.add_typer(flow_run_app, aliases=["flow-runs"])

LOGS_DEFAULT_PAGE_SIZE = 200


async def _get_flow_run_by_id_or_name(
    client: "PrefectClient",
    id_or_name: str,
) -> "FlowRun":
    """
    Resolve a flow run identifier that could be either a UUID or a name.

    Flow run names are not guaranteed to be unique, so this function will
    error if multiple flow runs match the given name.

    Args:
        client: The Prefect client to use for API calls
        id_or_name: Either a UUID string or a flow run name

    Returns:
        The matching FlowRun object

    Raises:
        typer.Exit: If flow run not found, or if multiple flow runs match the name
    """
    from prefect.client.schemas.filters import FlowRunFilterName

    # First, try parsing as UUID
    try:
        flow_run_id = UUID(id_or_name)
        try:
            return await client.read_flow_run(flow_run_id)
        except ObjectNotFound:
            exit_with_error(f"Flow run '{id_or_name}' not found!")
    except ValueError:
        # Not a valid UUID, treat as a name
        pass

    # Query by name (exact match)
    flow_runs = await client.read_flow_runs(
        flow_run_filter=FlowRunFilter(name=FlowRunFilterName(any_=[id_or_name])),
        limit=100,  # Reasonable limit for displaying matches
    )

    if not flow_runs:
        exit_with_error(f"Flow run '{id_or_name}' not found!")

    if len(flow_runs) == 1:
        return flow_runs[0]

    # Multiple matches - show all and exit with error
    lines = [f"Multiple flow runs found with name '{id_or_name}':\n"]
    for fr in flow_runs:
        state_name = fr.state.name if fr.state else "unknown"
        timestamp = fr.start_time or fr.created
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S") if timestamp else "N/A"
        lines.append(f"  - {fr.id} ({state_name}, {timestamp_str})")

    lines.append("\nPlease retry using an explicit flow run ID.")
    exit_with_error("\n".join(lines))


LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS = 20

logger: "logging.Logger" = get_logger(__name__)


@flow_run_app.command()
async def inspect(
    id: UUID,
    web: bool = typer.Option(
        False,
        "--web",
        help="Open the flow run in a web browser.",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Specify an output format. Currently supports: json",
    ),
):
    """
    View details about a flow run.
    """
    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    async with get_client() as client:
        try:
            flow_run = await client.read_flow_run(id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                exit_with_error(f"Flow run {id!r} not found!")
            else:
                raise

    if web:
        flow_run_url = url_for("flow-run", obj_id=id)
        if not flow_run_url:
            exit_with_error(
                "Failed to generate URL for flow run. Make sure PREFECT_UI_URL is configured."
            )

        await run_sync_in_worker_thread(webbrowser.open_new_tab, flow_run_url)
        exit_with_success(f"Opened flow run {id!r} in browser.")
    else:
        if output and output.lower() == "json":
            flow_run_json = flow_run.model_dump(mode="json")
            json_output = orjson.dumps(
                flow_run_json, option=orjson.OPT_INDENT_2
            ).decode()
            app.console.print(json_output)
        else:
            app.console.print(Pretty(flow_run))


@flow_run_app.command()
async def ls(
    flow_name: List[str] = typer.Option(None, help="Name of the flow"),
    limit: int = typer.Option(15, help="Maximum number of flow runs to list"),
    state: List[str] = typer.Option(None, help="Name of the flow run's state"),
    state_type: List[str] = typer.Option(None, help="Type of the flow run's state"),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Specify an output format. Currently supports: json",
    ),
):
    """
    View recent flow runs or flow runs for specific flows.

    Arguments:

        flow_name: Name of the flow

        limit: Maximum number of flow runs to list. Defaults to 15.

        state: Name of the flow run's state. Can be provided multiple times. Options are 'SCHEDULED', 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CRASHED', 'CANCELLING', 'CANCELLED', 'PAUSED', 'SUSPENDED', 'AWAITINGRETRY', 'RETRYING', and 'LATE'.

        state_type: Type of the flow run's state. Can be provided multiple times. Options are 'SCHEDULED', 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CRASHED', 'CANCELLING', 'CANCELLED', 'CRASHED', and 'PAUSED'.

    Examples:

    $ prefect flow-runs ls --state Running

    $ prefect flow-runs ls --state Running --state late

    $ prefect flow-runs ls --state-type RUNNING

    $ prefect flow-runs ls --state-type RUNNING --state-type FAILED
    """
    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    # Handling `state` and `state_type` argument validity in the function instead of by specifying
    # List[StateType] and List[StateName] in the type hints, allows users to provide
    # case-insensitive arguments for `state` and `state_type`.

    prefect_state_names = {
        "SCHEDULED": "Scheduled",
        "PENDING": "Pending",
        "RUNNING": "Running",
        "COMPLETED": "Completed",
        "FAILED": "Failed",
        "CANCELLED": "Cancelled",
        "CRASHED": "Crashed",
        "PAUSED": "Paused",
        "CANCELLING": "Cancelling",
        "SUSPENDED": "Suspended",
        "AWAITINGRETRY": "AwaitingRetry",
        "RETRYING": "Retrying",
        "LATE": "Late",
    }

    state_filter = {}
    formatted_states = []

    if state:
        for s in state:
            uppercased_state = s.upper()
            if uppercased_state in prefect_state_names:
                capitalized_state = prefect_state_names[uppercased_state]
                formatted_states.append(capitalized_state)
            else:
                # Do not change the case of the state name if it is not one of the official Prefect state names
                formatted_states.append(s)
                logger.warning(
                    f"State name {repr(s)} is not one of the official Prefect state names."
                )

        state_filter["name"] = {"any_": formatted_states}

    if state_type:
        upper_cased_states = [s.upper() for s in state_type]
        if not all(s in StateType.__members__ for s in upper_cased_states):
            exit_with_error(
                f"Invalid state type. Options are {', '.join(StateType.__members__)}."
            )

        state_filter["type"] = {
            "any_": [StateType[s].value for s in upper_cased_states]
        }

    async with get_client() as client:
        flow_runs = await client.read_flow_runs(
            flow_filter=FlowFilter(name={"any_": flow_name}) if flow_name else None,
            flow_run_filter=FlowRunFilter(state=state_filter) if state_filter else None,
            limit=limit,
            sort=FlowRunSort.EXPECTED_START_TIME_DESC,
        )
        flows_by_id = {
            flow.id: flow
            for flow in await client.read_flows(
                flow_filter=FlowFilter(id={"any_": [run.flow_id for run in flow_runs]})
            )
        }

        if not flow_runs:
            if output and output.lower() == "json":
                app.console.print("[]")
                return
            exit_with_success("No flow runs found.")

    if output and output.lower() == "json":
        flow_runs_json = [flow_run.model_dump(mode="json") for flow_run in flow_runs]
        json_output = orjson.dumps(flow_runs_json, option=orjson.OPT_INDENT_2).decode()
        app.console.print(json_output)
    else:
        table = Table(title="Flow Runs")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Flow", style="blue", no_wrap=True)
        table.add_column("Name", style="green", no_wrap=True)
        table.add_column("State", no_wrap=True)
        table.add_column("When", style="bold", no_wrap=True)

        for flow_run in sorted(flow_runs, key=lambda d: d.created, reverse=True):
            flow = flows_by_id[flow_run.flow_id]
            timestamp = (
                flow_run.state.state_details.scheduled_time
                if flow_run.state.is_scheduled()
                else flow_run.state.timestamp
            )
            table.add_row(
                str(flow_run.id),
                str(flow.name),
                str(flow_run.name),
                str(flow_run.state.type.value),
                human_friendly_diff(timestamp),
            )

        app.console.print(table)


@flow_run_app.command()
async def delete(id: UUID):
    """
    Delete a flow run by ID.
    """
    async with get_client() as client:
        try:
            if is_interactive() and not typer.confirm(
                (f"Are you sure you want to delete flow run with id {id!r}?"),
                default=False,
            ):
                exit_with_error("Deletion aborted.")
            await client.delete_flow_run(id)
        except ObjectNotFound:
            exit_with_error(f"Flow run '{id}' not found!")

    exit_with_success(f"Successfully deleted flow run '{id}'.")


@flow_run_app.command()
async def cancel(id: UUID):
    """Cancel a flow run by ID."""
    async with get_client() as client:
        cancelling_state = State(type=StateType.CANCELLING)
        try:
            result = await client.set_flow_run_state(
                flow_run_id=id, state=cancelling_state
            )
        except ObjectNotFound:
            exit_with_error(f"Flow run '{id}' not found!")

    if result.status == SetStateStatus.ABORT:
        exit_with_error(
            f"Flow run '{id}' was unable to be cancelled. Reason:"
            f" '{result.details.reason}'"
        )

    exit_with_success(f"Flow run '{id}' was successfully scheduled for cancellation.")


@flow_run_app.command()
async def retry(
    id_or_name: str = typer.Argument(
        ...,
        help="The flow run ID (UUID) or name to retry.",
    ),
    entrypoint: Optional[str] = typer.Option(
        None,
        "--entrypoint",
        "-e",
        help=(
            "The path to a file containing the flow to run, and the name of the flow "
            "function, in the format `path/to/file.py:flow_function_name`. "
            "Required if the flow run does not have an associated deployment."
        ),
    ),
):
    """
    Retry a failed or completed flow run.

    The flow run can be specified by either its UUID or its name. If multiple
    flow runs have the same name, you must use the UUID to disambiguate.

    If the flow run has an associated deployment, it will be scheduled for retry
    and a worker will pick it up. If there is no deployment, you must provide
    an --entrypoint to the flow code, and the flow will execute locally.

    \b
    Examples:
        $ prefect flow-run retry abc123-def456-7890-...
        $ prefect flow-run retry my-flow-run-name
        $ prefect flow-run retry abc123 --entrypoint ./flows/my_flow.py:my_flow
    """
    from prefect.flow_engine import run_flow
    from prefect.flows import load_flow_from_entrypoint
    from prefect.states import Scheduled

    terminal_states = {
        StateType.COMPLETED,
        StateType.FAILED,
        StateType.CANCELLED,
        StateType.CRASHED,
    }

    async with get_client() as client:
        # Resolve flow run by ID or name
        flow_run = await _get_flow_run_by_id_or_name(client, id_or_name)
        flow_run_id = flow_run.id

        # Validate flow run is in terminal state
        if flow_run.state is None or flow_run.state.type not in terminal_states:
            current_state = flow_run.state.type.value if flow_run.state else "unknown"
            exit_with_error(
                f"Flow run '{flow_run_id}' is in state '{current_state}' and cannot be retried. "
                f"Only flow runs in terminal states (COMPLETED, FAILED, CANCELLED, CRASHED) can be retried."
            )

        # Branch based on deployment association
        if flow_run.deployment_id:
            # Deployment-based retry: set state to Scheduled and exit
            # Use force=True to bypass orchestration rules that prevent state transitions
            # from terminal states (e.g., CANCELLED -> SCHEDULED)
            scheduled_state = Scheduled(message="Retried via CLI")
            try:
                result = await client.set_flow_run_state(
                    flow_run_id=flow_run_id, state=scheduled_state, force=True
                )
            except ObjectNotFound:
                exit_with_error(f"Flow run '{flow_run_id}' not found!")

            if result.status == SetStateStatus.ABORT:
                exit_with_error(
                    f"Flow run '{flow_run_id}' could not be retried. Reason: '{result.details.reason}'"
                )

            exit_with_success(
                f"Flow run '{flow_run_id}' has been scheduled for retry. "
                "A worker will pick it up shortly."
            )
        else:
            # Local retry: require entrypoint and execute synchronously
            if not entrypoint:
                exit_with_error(
                    f"Flow run '{flow_run_id}' does not have an associated deployment. "
                    "Please provide an --entrypoint to the flow code.\n\n"
                    f"Example: prefect flow-run retry {flow_run_id} --entrypoint ./flows/my_flow.py:my_flow"
                )

            # Load the flow from entrypoint
            try:
                flow = load_flow_from_entrypoint(entrypoint, use_placeholder_flow=False)
            except Exception as exc:
                exit_with_error(
                    f"Failed to load flow from entrypoint '{entrypoint}': {exc}"
                )

            # Check if this is an infrastructure-bound flow
            from prefect.flows import InfrastructureBoundFlow

            if isinstance(flow, InfrastructureBoundFlow):
                app.console.print(
                    f"Retrying flow run '{flow_run_id}' on remote infrastructure "
                    f"(work pool: {flow.work_pool})..."
                )

                try:
                    # Use the retry method which handles remote execution
                    await flow.retry(flow_run)
                except Exception as exc:
                    exit_with_error(f"Flow run failed: {exc}")

                # Re-fetch to get final state
                flow_run = await client.read_flow_run(flow_run_id)
                final_state = flow_run.state.type.value if flow_run.state else "unknown"

                if flow_run.state and flow_run.state.is_completed():
                    exit_with_success(
                        f"Flow run '{flow_run_id}' completed successfully."
                    )
                else:
                    exit_with_error(
                        f"Flow run '{flow_run_id}' finished with state: {final_state}"
                    )
            else:
                # Regular local execution path
                # Set state to Scheduled with force=True to bypass deployment check
                scheduled_state = Scheduled(message="Retried via CLI (local execution)")
                try:
                    result = await client.set_flow_run_state(
                        flow_run_id=flow_run_id, state=scheduled_state, force=True
                    )
                except ObjectNotFound:
                    exit_with_error(f"Flow run '{flow_run_id}' not found!")

                if result.status == SetStateStatus.ABORT:
                    exit_with_error(
                        f"Flow run '{flow_run_id}' could not be retried. Reason: '{result.details.reason}'"
                    )

                app.console.print(f"Executing flow run '{flow_run_id}' locally...")

                # Re-fetch the flow run to get updated state
                flow_run = await client.read_flow_run(flow_run_id)

                try:
                    call_args, call_kwargs = parameters_to_args_kwargs(
                        flow.fn, flow_run.parameters if flow_run else {}
                    )
                    parameters = get_call_parameters(flow.fn, call_args, call_kwargs)
                except Exception as exc:
                    state = await exception_to_crashed_state(exc)
                    await client.set_flow_run_state(
                        flow_run_id=flow_run_id, state=state, force=True
                    )
                    exit_with_error(
                        "Failed to use parameters from previous attempt. Please ensure the flow signature has not changed since the last run."
                    )

                # Execute the flow synchronously, reusing the existing flow run
                try:
                    run_flow(
                        flow=flow,
                        flow_run=flow_run,
                        return_type="state",
                        parameters=parameters,
                    )
                except Exception as exc:
                    exit_with_error(f"Flow run failed: {exc}")

                # Re-fetch to get final state
                flow_run = await client.read_flow_run(flow_run_id)
                final_state = flow_run.state.type.value if flow_run.state else "unknown"

                if flow_run.state and flow_run.state.is_completed():
                    exit_with_success(
                        f"Flow run '{flow_run_id}' completed successfully."
                    )
                else:
                    exit_with_error(
                        f"Flow run '{flow_run_id}' finished with state: {final_state}"
                    )


@flow_run_app.command()
async def logs(
    id: UUID,
    head: bool = typer.Option(
        False,
        "--head",
        "-h",
        help=(
            f"Show the first {LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS} logs instead of"
            " all logs."
        ),
    ),
    num_logs: int = typer.Option(
        None,
        "--num-logs",
        "-n",
        help=(
            "Number of logs to show when using the --head or --tail flag. If None,"
            f" defaults to {LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS}."
        ),
        min=1,
    ),
    reverse: bool = typer.Option(
        False,
        "--reverse",
        "-r",
        help="Reverse the logs order to print the most recent logs first",
    ),
    tail: bool = typer.Option(
        False,
        "--tail",
        "-t",
        help=(
            f"Show the last {LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS} logs instead of"
            " all logs."
        ),
    ),
):
    """
    View logs for a flow run.
    """
    # Pagination - API returns max 200 (LOGS_DEFAULT_PAGE_SIZE) logs at a time
    offset = 0
    more_logs = True
    num_logs_returned = 0

    # if head and tail flags are being used together
    if head and tail:
        exit_with_error("Please provide either a `head` or `tail` option but not both.")

    user_specified_num_logs = (
        num_logs or LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS
        if head or tail or num_logs
        else None
    )

    # if using tail update offset according to LOGS_DEFAULT_PAGE_SIZE
    if tail:
        offset = max(0, user_specified_num_logs - LOGS_DEFAULT_PAGE_SIZE)

    log_filter = LogFilter(flow_run_id={"any_": [id]})

    async with get_client() as client:
        # Get the flow run
        try:
            flow_run = await client.read_flow_run(id)
        except ObjectNotFound:
            exit_with_error(f"Flow run {str(id)!r} not found!")

        while more_logs:
            num_logs_to_return_from_page = (
                LOGS_DEFAULT_PAGE_SIZE
                if user_specified_num_logs is None
                else min(
                    LOGS_DEFAULT_PAGE_SIZE, user_specified_num_logs - num_logs_returned
                )
            )

            # Get the next page of logs
            page_logs = await client.read_logs(
                log_filter=log_filter,
                limit=num_logs_to_return_from_page,
                offset=offset,
                sort=(
                    LogSort.TIMESTAMP_DESC if reverse or tail else LogSort.TIMESTAMP_ASC
                ),
            )

            for log in reversed(page_logs) if tail and not reverse else page_logs:
                # Print following the flow run format (declared in logging.yml)
                timestamp = f"{log.timestamp:%Y-%m-%d %H:%M:%S.%f}"[:-3]
                log_level = f"{logging.getLevelName(log.level):7s}"
                flow_run_info = f"Flow run {flow_run.name!r} - {escape(log.message)}"

                log_message = f"{timestamp} | {log_level} | {flow_run_info}"
                app.console.print(
                    log_message,
                    soft_wrap=True,
                )

            # Update the number of logs retrieved
            num_logs_returned += num_logs_to_return_from_page

            if tail:
                #  If the current offset is not 0, update the offset for the next page
                if offset != 0:
                    offset = (
                        0
                        # Reset the offset to 0 if there are less logs than the LOGS_DEFAULT_PAGE_SIZE to get the remaining log
                        if offset < LOGS_DEFAULT_PAGE_SIZE
                        else offset - LOGS_DEFAULT_PAGE_SIZE
                    )
                else:
                    more_logs = False
            else:
                if len(page_logs) == LOGS_DEFAULT_PAGE_SIZE:
                    offset += LOGS_DEFAULT_PAGE_SIZE
                else:
                    # No more logs to show, exit
                    more_logs = False


@flow_run_app.command()
async def execute(
    id: Optional[UUID] = typer.Argument(None, help="ID of the flow run to execute"),
):
    if id is None:
        environ_flow_id = os.environ.get("PREFECT__FLOW_RUN_ID")
        if environ_flow_id:
            id = UUID(environ_flow_id)

    if id is None:
        exit_with_error("Could not determine the ID of the flow run to execute.")

    runner = Runner()

    def _handle_reschedule_sigterm(_signal: int, _frame: FrameType | None):
        logger.info("SIGTERM received, initiating graceful shutdown...")
        runner.reschedule_current_flow_runs()
        exit_with_success("Flow run successfully rescheduled.")

    # Set up signal handling to reschedule run on SIGTERM
    on_sigterm = os.environ.get("PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR", "").lower()
    if (
        threading.current_thread() is threading.main_thread()
        and on_sigterm == "reschedule"
    ):
        signal.signal(signal.SIGTERM, _handle_reschedule_sigterm)

    await runner.execute_flow_run(id)
