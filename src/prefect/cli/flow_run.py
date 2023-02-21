"""
Command line interface for working with flow runs
"""
import logging
from typing import List
from uuid import UUID

import httpx
import pendulum
import typer
from fastapi import status
from rich.pretty import Pretty
from rich.table import Table

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client.orchestration import get_client
from prefect.exceptions import ObjectNotFound
from prefect.server.schemas.filters import FlowFilter, FlowRunFilter, LogFilter
from prefect.server.schemas.responses import SetStateStatus
from prefect.server.schemas.sorting import FlowRunSort
from prefect.server.schemas.states import StateType
from prefect.states import State

flow_run_app = PrefectTyper(
    name="flow-run", help="Commands for interacting with flow runs."
)
app.add_typer(flow_run_app, aliases=["flow-runs"])

LOGS_DEFAULT_PAGE_SIZE = 200
LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS = 20


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
    state_type: List[StateType] = typer.Option(
        None, help="Type of the flow run's state"
    ),
):
    """
    View recent flow runs or flow runs for specific flows
    """

    state_filter = {}
    if state:
        state_filter["name"] = {"any_": state}
    if state_type:
        state_filter["type"] = {"any_": state_type}

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
            pendulum.instance(timestamp).diff_for_humans(),
        )

    app.console.print(table)


@flow_run_app.command()
async def delete(id: UUID):
    """
    Delete a flow run by ID.
    """
    async with get_client() as client:
        try:
            await client.delete_flow_run(id)
        except ObjectNotFound as exc:
            exit_with_error(f"Flow run '{id}' not found!")

    exit_with_success(f"Successfully deleted flow run '{id}'.")


@flow_run_app.command()
async def cancel(id: UUID):
    """Cancel a flow fun by ID."""
    async with get_client() as client:
        cancelling_state = State(type=StateType.CANCELLING)
        try:
            result = await client.set_flow_run_state(
                flow_run_id=id, state=cancelling_state
            )
        except ObjectNotFound as exc:
            exit_with_error(f"Flow run '{id}' not found!")

    if result.status == SetStateStatus.ABORT:
        exit_with_error(
            f"Flow run '{id}' was unable to be cancelled. Reason:"
            f" '{result.details.reason}'"
        )

    exit_with_success(f"Flow run '{id}' was succcessfully scheduled for cancellation.")


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
            "Number of logs to show when using the --head flag. If None, defaults to"
            f" {LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS}."
        ),
        min=1,
    ),
):
    """
    View logs for a flow run.
    """
    # Pagination - API returns max 200 (LOGS_DEFAULT_PAGE_SIZE) logs at a time
    offset = 0
    more_logs = True
    num_logs_returned = 0

    # If head is specified, we need to stop after we've retrieved enough logs
    if head or num_logs:
        user_specified_num_logs = num_logs or LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS
    else:
        user_specified_num_logs = None

    log_filter = LogFilter(flow_run_id={"any_": [id]})

    async with get_client() as client:
        # Get the flow run
        try:
            flow_run = await client.read_flow_run(id)
        except ObjectNotFound as exc:
            exit_with_error(f"Flow run {str(id)!r} not found!")

        while more_logs:
            num_logs_to_return_from_page = (
                LOGS_DEFAULT_PAGE_SIZE
                if user_specified_num_logs is None
                else min(LOGS_DEFAULT_PAGE_SIZE, user_specified_num_logs)
            )

            # Get the next page of logs
            page_logs = await client.read_logs(
                log_filter=log_filter, limit=num_logs_to_return_from_page, offset=offset
            )

            # Print the logs
            for log in page_logs:
                app.console.print(
                    # Print following the flow run format (declared in logging.yml)
                    (
                        f"{pendulum.instance(log.timestamp).to_datetime_string()}.{log.timestamp.microsecond // 1000:03d} |"
                        f" {logging.getLevelName(log.level):7s} | Flow run"
                        f" {flow_run.name!r} - {log.message}"
                    ),
                    soft_wrap=True,
                )

            # Update the number of logs retrieved
            num_logs_returned += num_logs_to_return_from_page

            if len(page_logs) == LOGS_DEFAULT_PAGE_SIZE:
                offset += LOGS_DEFAULT_PAGE_SIZE
            else:
                # No more logs to show, exit
                more_logs = False
