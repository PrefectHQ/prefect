"""
Task run command — native cyclopts implementation.

View and inspect task runs.
"""

import logging
import webbrowser
from typing import Annotated, Optional, cast
from uuid import UUID

import cyclopts

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

task_run_app: cyclopts.App = cyclopts.App(
    name="task-run",
    alias="task-runs",
    help="View and inspect task runs.",
    version_flags=[],
    help_flags=["--help"],
)

LOGS_DEFAULT_PAGE_SIZE = 200
LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS = 20


@task_run_app.command(name="inspect")
@with_cli_exception_handling
async def inspect(
    id: UUID,
    *,
    web: Annotated[
        bool,
        cyclopts.Parameter("--web", help="Open the task run in a web browser."),
    ] = False,
    output: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--output",
            alias="-o",
            help="Specify an output format. Currently supports: json",
        ),
    ] = None,
):
    """View details about a task run."""
    import orjson
    from rich.pretty import Pretty

    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound
    from prefect.utilities.asyncutils import run_sync_in_worker_thread
    from prefect.utilities.urls import url_for

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    async with get_client() as client:
        try:
            task_run = await client.read_task_run(id)
        except ObjectNotFound:
            exit_with_error(f"Task run '{id}' not found!")

    if web:
        task_run_url = url_for("task-run", obj_id=id)
        if not task_run_url:
            exit_with_error(
                "Failed to generate URL for task run. Make sure PREFECT_UI_URL is configured."
            )

        await run_sync_in_worker_thread(webbrowser.open_new_tab, task_run_url)
        exit_with_success(f"Opened task run {id!r} in browser.")
    else:
        if output and output.lower() == "json":
            task_run_json = task_run.model_dump(mode="json")
            json_output = orjson.dumps(
                task_run_json, option=orjson.OPT_INDENT_2
            ).decode()
            _cli.console.print(json_output)
        else:
            _cli.console.print(Pretty(task_run))


@task_run_app.command(name="ls")
@with_cli_exception_handling
async def ls(
    *,
    task_run_name: Annotated[
        Optional[list[str]],
        cyclopts.Parameter("--task-run-name", help="Name of the task"),
    ] = None,
    limit: Annotated[
        int,
        cyclopts.Parameter("--limit", help="Maximum number of task runs to list"),
    ] = 15,
    state: Annotated[
        Optional[list[str]],
        cyclopts.Parameter("--state", help="Name of the task run's state"),
    ] = None,
    state_type: Annotated[
        Optional[list[str]],
        cyclopts.Parameter("--state-type", help="Type of the task run's state"),
    ] = None,
):
    """View recent task runs."""
    from datetime import datetime

    from rich.table import Table

    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import (
        TaskRunFilter,
        TaskRunFilterName,
        TaskRunFilterState,
        TaskRunFilterStateName,
        TaskRunFilterStateType,
    )
    from prefect.client.schemas.objects import StateType
    from prefect.client.schemas.sorting import TaskRunSort
    from prefect.types._datetime import human_friendly_diff

    # Validate state_type values
    valid_state_types = {st.value for st in StateType}
    if state_type:
        for st in state_type:
            if st.upper() not in valid_state_types:
                exit_with_error(
                    f"Invalid state type: {st!r}. "
                    f"Must be one of: {', '.join(sorted(valid_state_types))}"
                )

    parsed_state_types = (
        [StateType(st.upper()) for st in state_type] if state_type else None
    )

    if state or parsed_state_types:
        state_filter = TaskRunFilterState(
            name=TaskRunFilterStateName(any_=[s.capitalize() for s in state])
            if state
            else None,
            type=TaskRunFilterStateType(any_=parsed_state_types)
            if parsed_state_types
            else None,
        )
    else:
        state_filter = None

    async with get_client() as client:
        task_runs = await client.read_task_runs(
            task_run_filter=TaskRunFilter(
                name=TaskRunFilterName(any_=task_run_name) if task_run_name else None,
                state=state_filter,
            ),
            limit=limit,
            sort=TaskRunSort.EXPECTED_START_TIME_DESC,
        )

    if not task_runs:
        _cli.console.print("No task runs found.")
        return

    table = Table(title="Task Runs")
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Task", style="blue", no_wrap=True)
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("State", no_wrap=True)
    table.add_column("When", style="bold", no_wrap=True)

    for task_run in sorted(
        task_runs, key=lambda d: cast(datetime, d.created), reverse=True
    ):
        task = task_run
        if task_run.state:
            timestamp = (
                task_run.state.state_details.scheduled_time
                if task_run.state.is_scheduled()
                else task_run.state.timestamp
            )
        else:
            timestamp = task_run.created

        table.add_row(
            str(task_run.id),
            str(task.name),
            str(task_run.name),
            str(task_run.state.type.value) if task_run.state else "Unknown",
            human_friendly_diff(timestamp),
        )

    _cli.console.print(table)


@task_run_app.command(name="logs")
@with_cli_exception_handling
async def logs(
    id: UUID,
    *,
    head: Annotated[
        bool,
        cyclopts.Parameter(
            "--head",
            alias="-h",
            help=(
                f"Show the first {LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS} logs instead of"
                " all logs."
            ),
        ),
    ] = False,
    num_logs: Annotated[
        int,
        cyclopts.Parameter(
            "--num-logs",
            alias="-n",
            help=(
                "Number of logs to show when using the --head or --tail flag. If None,"
                f" defaults to {LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS}."
            ),
        ),
    ] = LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS,
    reverse: Annotated[
        bool,
        cyclopts.Parameter(
            "--reverse",
            alias="-r",
            help="Reverse the logs order to print the most recent logs first",
        ),
    ] = False,
    tail: Annotated[
        bool,
        cyclopts.Parameter(
            "--tail",
            alias="-t",
            help=(
                f"Show the last {LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS} logs instead of"
                " all logs."
            ),
        ),
    ] = False,
):
    """View logs for a task run."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import LogFilter, LogFilterTaskRunId
    from prefect.client.schemas.sorting import LogSort
    from prefect.exceptions import ObjectNotFound
    from prefect.types._datetime import to_datetime_string

    if num_logs < 1:
        exit_with_error("--num-logs must be >= 1.")

    offset = 0
    more_logs = True
    num_logs_returned = 0

    if head and tail:
        exit_with_error("Please provide either a `head` or `tail` option but not both.")

    if tail:
        offset = max(0, num_logs - LOGS_DEFAULT_PAGE_SIZE)

    log_filter = LogFilter(task_run_id=LogFilterTaskRunId(any_=[id]))

    async with get_client() as client:
        try:
            task_run = await client.read_task_run(id)
        except ObjectNotFound:
            exit_with_error(f"task run {str(id)!r} not found!")

        while more_logs:
            num_logs_to_return_from_page = min(
                LOGS_DEFAULT_PAGE_SIZE, num_logs - num_logs_returned
            )

            page_logs = await client.read_logs(
                log_filter=log_filter,
                limit=num_logs_to_return_from_page,
                offset=offset,
                sort=(
                    LogSort.TIMESTAMP_DESC if reverse or tail else LogSort.TIMESTAMP_ASC
                ),
            )

            for log in reversed(page_logs) if tail and not reverse else page_logs:
                _cli.console.print(
                    (
                        f"{to_datetime_string(log.timestamp)}.{log.timestamp.microsecond // 1000:03d} |"
                        f" {logging.getLevelName(log.level):7s} | Task run"
                        f" {task_run.name!r} - {log.message}"
                    ),
                    soft_wrap=True,
                )

            num_logs_returned += num_logs_to_return_from_page

            if tail:
                if offset != 0:
                    offset = (
                        0
                        if offset < LOGS_DEFAULT_PAGE_SIZE
                        else offset - LOGS_DEFAULT_PAGE_SIZE
                    )
                else:
                    more_logs = False
            else:
                if len(page_logs) == LOGS_DEFAULT_PAGE_SIZE:
                    offset += LOGS_DEFAULT_PAGE_SIZE
                else:
                    more_logs = False
