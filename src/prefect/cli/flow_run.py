"""
Command line interface for working with flow runs
"""

from __future__ import annotations

import logging
import os
import signal
import threading
from types import FrameType
from typing import List, Optional
from uuid import UUID

import httpx
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
from prefect.states import State
from prefect.types._datetime import human_friendly_diff

flow_run_app: PrefectTyper = PrefectTyper(
    name="flow-run", help="Interact with flow runs."
)
app.add_typer(flow_run_app, aliases=["flow-runs"])

LOGS_DEFAULT_PAGE_SIZE = 200
LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS = 20

logger: "logging.Logger" = get_logger(__name__)


@flow_run_app.command()
async def inspect(id: UUID):
    """
    View details about a flow run.
    """
    async with get_client() as client:
        try:
            flow_run = await client.read_flow_run(id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                exit_with_error(f"Flow run {id!r} not found!")
            else:
                raise

    app.console.print(Pretty(flow_run))


@flow_run_app.command()
async def ls(
    flow_name: List[str] = typer.Option(None, help="Name of the flow"),
    limit: int = typer.Option(15, help="Maximum number of flow runs to list"),
    state: List[str] = typer.Option(None, help="Name of the flow run's state"),
    state_type: List[str] = typer.Option(None, help="Type of the flow run's state"),
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
            exit_with_success("No flow runs found.")

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
