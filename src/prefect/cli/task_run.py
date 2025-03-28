"""
Command line interface for working with task runs
"""

import logging
from typing import List
from uuid import UUID

import httpx
import typer
from rich.pretty import Pretty
from rich.table import Table
from starlette import status

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import LogFilter, TaskRunFilter
from prefect.client.schemas.objects import StateType
from prefect.client.schemas.sorting import LogSort, TaskRunSort
from prefect.exceptions import ObjectNotFound
from prefect.types._datetime import (
    human_friendly_diff,
    to_datetime_string,
)

task_run_app: PrefectTyper = PrefectTyper(
    name="task-run", help="View and inspect task runs."
)
app.add_typer(task_run_app, aliases=["task-runs"])

LOGS_DEFAULT_PAGE_SIZE = 200
LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS = 20


@task_run_app.command()
async def inspect(id: UUID):
    """
    View details about a task run.
    """
    async with get_client() as client:
        try:
            task_run = await client.read_task_run(id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                exit_with_error(f"Task run {id!r} not found!")
            else:
                raise

    app.console.print(Pretty(task_run))


@task_run_app.command()
async def ls(
    task_run_name: List[str] = typer.Option(None, help="Name of the task"),
    limit: int = typer.Option(15, help="Maximum number of task runs to list"),
    state: List[str] = typer.Option(None, help="Name of the task run's state"),
    state_type: List[StateType] = typer.Option(
        None, help="Type of the task run's state"
    ),
):
    """
    View recent task runs
    """

    state_filter = {}
    if state:
        state_filter["name"] = {"any_": [s.capitalize() for s in state]}
    if state_type:
        state_filter["type"] = {"any_": state_type}

    async with get_client() as client:
        task_runs = await client.read_task_runs(
            task_run_filter=TaskRunFilter(
                name={"any_": task_run_name} if task_run_name else None,
                state=state_filter if state_filter else None,
            ),
            limit=limit,
            sort=TaskRunSort.EXPECTED_START_TIME_DESC,
        )

    table = Table(title="Task Runs")
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Task", style="blue", no_wrap=True)
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("State", no_wrap=True)
    table.add_column("When", style="bold", no_wrap=True)

    for task_run in sorted(task_runs, key=lambda d: d.created, reverse=True):
        task = task_run
        timestamp = (
            task_run.state.state_details.scheduled_time
            if task_run.state.is_scheduled()
            else task_run.state.timestamp
        )
        table.add_row(
            str(task_run.id),
            str(task.name),
            str(task_run.name),
            str(task_run.state.type.value),
            human_friendly_diff(timestamp),
        )

    app.console.print(table)


@task_run_app.command()
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
    View logs for a task run.
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

    log_filter = LogFilter(task_run_id={"any_": [id]})

    async with get_client() as client:
        # Get the task run
        try:
            task_run = await client.read_task_run(id)
        except ObjectNotFound:
            exit_with_error(f"task run {str(id)!r} not found!")

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
                app.console.print(
                    # Print following the task run format (declared in logging.yml)
                    (
                        f"{to_datetime_string(log.timestamp)}.{log.timestamp.microsecond // 1000:03d} |"
                        f" {logging.getLevelName(log.level):7s} | Task run"
                        f" {task_run.name!r} - {log.message}"
                    ),
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
