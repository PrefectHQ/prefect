"""
Flow run command — native cyclopts implementation.

Interact with flow runs.
"""

import logging
import os
import signal
import threading
import webbrowser
from types import FrameType
from typing import Annotated, Optional
from uuid import UUID

import cyclopts
from rich.markup import escape
from rich.pretty import Pretty
from rich.table import Table

from prefect.cli._cyclopts._utilities import (
    exit_with_error,
    exit_with_success,
    run_async,
    with_cli_exception_handling,
)

flow_run_app = cyclopts.App(name="flow-run", help="Interact with flow runs.")

LOGS_DEFAULT_PAGE_SIZE = 200
LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS = 20


def _get_console():
    from prefect.cli._cyclopts import console

    return console


def _is_interactive():
    from prefect.cli._cyclopts import _is_interactive

    return _is_interactive()


@flow_run_app.command()
@with_cli_exception_handling
@run_async
async def inspect(
    id: UUID,
    *,
    web: Annotated[
        bool,
        cyclopts.Parameter("--web", help="Open the flow run in a web browser."),
    ] = False,
    output: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--output", alias="-o", help="Output format. Supports: json"
        ),
    ] = None,
):
    """View details about a flow run."""
    import httpx
    import orjson
    from starlette import status

    from prefect.client.orchestration import get_client
    from prefect.utilities.asyncutils import run_sync_in_worker_thread
    from prefect.utilities.urls import url_for

    console = _get_console()

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
                "Failed to generate URL for flow run. "
                "Make sure PREFECT_UI_URL is configured."
            )
        await run_sync_in_worker_thread(webbrowser.open_new_tab, flow_run_url)
        exit_with_success(f"Opened flow run {id!r} in browser.")
    else:
        if output and output.lower() == "json":
            flow_run_json = flow_run.model_dump(mode="json")
            json_output = orjson.dumps(
                flow_run_json, option=orjson.OPT_INDENT_2
            ).decode()
            console.print(json_output)
        else:
            console.print(Pretty(flow_run))


@flow_run_app.command()
@with_cli_exception_handling
@run_async
async def ls(
    *,
    flow_name: Annotated[
        Optional[list[str]],
        cyclopts.Parameter("--flow-name", help="Name of the flow (repeatable)."),
    ] = None,
    limit: Annotated[
        int,
        cyclopts.Parameter("--limit", help="Maximum number of flow runs to list."),
    ] = 15,
    state: Annotated[
        Optional[list[str]],
        cyclopts.Parameter("--state", help="Filter by state name (repeatable)."),
    ] = None,
    state_type: Annotated[
        Optional[list[str]],
        cyclopts.Parameter("--state-type", help="Filter by state type (repeatable)."),
    ] = None,
    output: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--output", alias="-o", help="Output format. Supports: json"
        ),
    ] = None,
):
    """View recent flow runs or flow runs for specific flows."""
    import orjson

    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import FlowFilter, FlowRunFilter
    from prefect.client.schemas.objects import StateType
    from prefect.client.schemas.sorting import FlowRunSort
    from prefect.logging import get_logger
    from prefect.types._datetime import human_friendly_diff

    logger = get_logger(__name__)
    console = _get_console()

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

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
                formatted_states.append(prefect_state_names[uppercased_state])
            else:
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
            flow_run_filter=(
                FlowRunFilter(state=state_filter) if state_filter else None
            ),
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
                console.print("[]")
                return
            exit_with_success("No flow runs found.")

    if output and output.lower() == "json":
        flow_runs_json = [flow_run.model_dump(mode="json") for flow_run in flow_runs]
        json_output = orjson.dumps(flow_runs_json, option=orjson.OPT_INDENT_2).decode()
        console.print(json_output)
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

        console.print(table)


@flow_run_app.command()
@with_cli_exception_handling
@run_async
async def delete(id: UUID):
    """Delete a flow run by ID."""
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    async with get_client() as client:
        try:
            if _is_interactive():
                from rich.prompt import Confirm

                if not Confirm.ask(
                    f"Are you sure you want to delete flow run with id {id!r}?",
                    console=_get_console(),
                    default=False,
                ):
                    exit_with_error("Deletion aborted.")
            await client.delete_flow_run(id)
        except ObjectNotFound:
            exit_with_error(f"Flow run '{id}' not found!")

    exit_with_success(f"Successfully deleted flow run '{id}'.")


@flow_run_app.command()
@with_cli_exception_handling
@run_async
async def cancel(id: UUID):
    """Cancel a flow run by ID."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.objects import StateType
    from prefect.client.schemas.responses import SetStateStatus
    from prefect.exceptions import ObjectNotFound
    from prefect.states import State

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
@with_cli_exception_handling
@run_async
async def retry(
    id_or_name: Annotated[
        str,
        cyclopts.Parameter(help="The flow run ID (UUID) or name to retry."),
    ],
    *,
    entrypoint: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--entrypoint",
            alias="-e",
            help="Path to flow file in format path/to/file.py:flow_function_name.",
        ),
    ] = None,
):
    """Retry a failed or completed flow run."""
    from prefect.cli.flow_run import _get_flow_run_by_id_or_name
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.objects import StateType
    from prefect.client.schemas.responses import SetStateStatus
    from prefect.exceptions import ObjectNotFound
    from prefect.flow_engine import run_flow
    from prefect.flows import InfrastructureBoundFlow, load_flow_from_entrypoint
    from prefect.states import Scheduled, exception_to_crashed_state
    from prefect.utilities.callables import (
        get_call_parameters,
        parameters_to_args_kwargs,
    )

    console = _get_console()

    terminal_states = {
        StateType.COMPLETED,
        StateType.FAILED,
        StateType.CANCELLED,
        StateType.CRASHED,
    }

    async with get_client() as client:
        flow_run = await _get_flow_run_by_id_or_name(client, id_or_name)
        flow_run_id = flow_run.id

        if flow_run.state is None or flow_run.state.type not in terminal_states:
            current_state = flow_run.state.type.value if flow_run.state else "unknown"
            exit_with_error(
                f"Flow run '{flow_run_id}' is in state '{current_state}' and cannot be retried. "
                f"Only flow runs in terminal states (COMPLETED, FAILED, CANCELLED, CRASHED) can be retried."
            )

        if flow_run.deployment_id:
            scheduled_state = Scheduled(message="Retried via CLI")
            try:
                result = await client.set_flow_run_state(
                    flow_run_id=flow_run_id, state=scheduled_state, force=True
                )
            except ObjectNotFound:
                exit_with_error(f"Flow run '{flow_run_id}' not found!")

            if result.status == SetStateStatus.ABORT:
                exit_with_error(
                    f"Flow run '{flow_run_id}' could not be retried. "
                    f"Reason: '{result.details.reason}'"
                )

            exit_with_success(
                f"Flow run '{flow_run_id}' has been scheduled for retry. "
                "A worker will pick it up shortly."
            )
        else:
            if not entrypoint:
                exit_with_error(
                    f"Flow run '{flow_run_id}' does not have an associated deployment. "
                    "Please provide an --entrypoint to the flow code.\n\n"
                    f"Example: prefect flow-run retry {flow_run_id} "
                    "--entrypoint ./flows/my_flow.py:my_flow"
                )

            try:
                flow = load_flow_from_entrypoint(entrypoint, use_placeholder_flow=False)
            except Exception as exc:
                exit_with_error(
                    f"Failed to load flow from entrypoint '{entrypoint}': {exc}"
                )

            if isinstance(flow, InfrastructureBoundFlow):
                console.print(
                    f"Retrying flow run '{flow_run_id}' on remote infrastructure "
                    f"(work pool: {flow.work_pool})..."
                )
                try:
                    await flow.retry(flow_run)
                except Exception as exc:
                    exit_with_error(f"Flow run failed: {exc}")

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
                scheduled_state = Scheduled(message="Retried via CLI (local execution)")
                try:
                    result = await client.set_flow_run_state(
                        flow_run_id=flow_run_id,
                        state=scheduled_state,
                        force=True,
                    )
                except ObjectNotFound:
                    exit_with_error(f"Flow run '{flow_run_id}' not found!")

                if result.status == SetStateStatus.ABORT:
                    exit_with_error(
                        f"Flow run '{flow_run_id}' could not be retried. "
                        f"Reason: '{result.details.reason}'"
                    )

                console.print(f"Executing flow run '{flow_run_id}' locally...")

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
                        "Failed to use parameters from previous attempt. "
                        "Please ensure the flow signature has not changed "
                        "since the last run."
                    )

                try:
                    run_flow(
                        flow=flow,
                        flow_run=flow_run,
                        return_type="state",
                        parameters=parameters,
                    )
                except Exception as exc:
                    exit_with_error(f"Flow run failed: {exc}")

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
@with_cli_exception_handling
@run_async
async def logs(
    id: UUID,
    *,
    head: Annotated[
        bool,
        cyclopts.Parameter(
            "--head",
            alias="-h",
            help=f"Show the first {LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS} logs.",
        ),
    ] = False,
    num_logs: Annotated[
        Optional[int],
        cyclopts.Parameter(
            "--num-logs",
            alias="-n",
            help="Number of logs to show with --head or --tail.",
        ),
    ] = None,
    reverse: Annotated[
        bool,
        cyclopts.Parameter(
            "--reverse", alias="-r", help="Reverse log order (most recent first)."
        ),
    ] = False,
    tail: Annotated[
        bool,
        cyclopts.Parameter(
            "--tail",
            alias="-t",
            help=f"Show the last {LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS} logs.",
        ),
    ] = False,
):
    """View logs for a flow run."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import LogFilter
    from prefect.client.schemas.sorting import LogSort
    from prefect.exceptions import ObjectNotFound

    console = _get_console()

    offset = 0
    more_logs = True
    num_logs_returned = 0

    if head and tail:
        exit_with_error("Please provide either a `head` or `tail` option but not both.")

    user_specified_num_logs = (
        num_logs or LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS
        if head or tail or num_logs
        else None
    )

    if tail:
        offset = max(0, user_specified_num_logs - LOGS_DEFAULT_PAGE_SIZE)

    log_filter = LogFilter(flow_run_id={"any_": [id]})

    async with get_client() as client:
        try:
            flow_run = await client.read_flow_run(id)
        except ObjectNotFound:
            exit_with_error(f"Flow run {str(id)!r} not found!")

        while more_logs:
            num_logs_to_return_from_page = (
                LOGS_DEFAULT_PAGE_SIZE
                if user_specified_num_logs is None
                else min(
                    LOGS_DEFAULT_PAGE_SIZE,
                    user_specified_num_logs - num_logs_returned,
                )
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
                timestamp = f"{log.timestamp:%Y-%m-%d %H:%M:%S.%f}"[:-3]
                log_level = f"{logging.getLevelName(log.level):7s}"
                flow_run_info = f"Flow run {flow_run.name!r} - {escape(log.message)}"
                log_message = f"{timestamp} | {log_level} | {flow_run_info}"
                console.print(log_message, soft_wrap=True)

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


@flow_run_app.command()
@with_cli_exception_handling
@run_async
async def execute(
    id: Annotated[
        Optional[UUID],
        cyclopts.Parameter(help="ID of the flow run to execute."),
    ] = None,
):
    """Execute a flow run by ID."""
    from prefect.logging import get_logger
    from prefect.runner import Runner

    logger = get_logger(__name__)

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

    on_sigterm = os.environ.get("PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR", "").lower()
    if (
        threading.current_thread() is threading.main_thread()
        and on_sigterm == "reschedule"
    ):
        signal.signal(signal.SIGTERM, _handle_reschedule_sigterm)

    await runner.execute_flow_run(id)
