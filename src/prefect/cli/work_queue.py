"""
Work queue command — native cyclopts implementation.

Manage work queues.
"""

from __future__ import annotations

import datetime
import warnings
from textwrap import dedent
from typing import Annotated, Optional, Union
from uuid import UUID

import cyclopts
import orjson
from rich.pretty import Pretty
from rich.table import Table

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

work_queue_app: cyclopts.App = cyclopts.App(
    name="work-queue",
    alias="work-queues",
    help="Manage work queues.",
    version_flags=[],
    help_flags=["--help"],
)


async def _get_work_queue_id_from_name_or_id(
    name_or_id: Union[UUID, str], work_pool_name: Optional[str] = None
) -> UUID:
    """For backwards-compatibility, the main argument can be a name or an ID."""
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    if not name_or_id:
        exit_with_error("Provide a work queue name.")

    try:
        return UUID(name_or_id)
    except (AttributeError, ValueError):
        async with get_client() as client:
            try:
                work_queue = await client.read_work_queue_by_name(
                    name=name_or_id,
                    work_pool_name=work_pool_name,
                )
                return work_queue.id
            except ObjectNotFound:
                if not work_pool_name:
                    exit_with_error(f"No work queue named {name_or_id!r} found.")

                exit_with_error(
                    f"No work queue named {name_or_id!r} found in work pool"
                    f" {work_pool_name!r}."
                )


@work_queue_app.command(name="create")
@with_cli_exception_handling
async def create(
    name: Annotated[
        str, cyclopts.Parameter(help="The unique name to assign this work queue")
    ],
    *,
    limit: Annotated[
        Optional[int],
        cyclopts.Parameter(
            "--limit", alias="-l", help="The concurrency limit to set on the queue."
        ),
    ] = None,
    pool: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--pool",
            alias="-p",
            help="The name of the work pool to create the work queue in.",
        ),
    ] = None,
    priority: Annotated[
        Optional[int],
        cyclopts.Parameter(
            "--priority",
            alias="-q",
            help="The associated priority for the created work queue",
        ),
    ] = None,
):
    """Create a work queue."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.objects import DEFAULT_AGENT_WORK_POOL_NAME
    from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound

    async with get_client() as client:
        try:
            result = await client.create_work_queue(
                name=name, work_pool_name=pool, priority=priority
            )
            if limit is not None:
                await client.update_work_queue(
                    id=result.id,
                    concurrency_limit=limit,
                )
        except ObjectAlreadyExists:
            exit_with_error(f"Work queue with name: {name!r} already exists.")
        except ObjectNotFound:
            exit_with_error(f"Work pool with name: {pool!r} not found.")

    if not pool:
        pool = DEFAULT_AGENT_WORK_POOL_NAME
    output_msg = dedent(
        f"""
        Created work queue with properties:
            name - {name!r}
            work pool - {pool!r}
            id - {result.id}
            concurrency limit - {limit}
        Start a worker to pick up flow runs from the work queue:
            prefect worker start -q '{result.name} -p {pool}'

        Inspect the work queue:
            prefect work-queue inspect '{result.name}'
        """
    )
    exit_with_success(output_msg)


@work_queue_app.command(name="set-concurrency-limit")
@with_cli_exception_handling
async def set_concurrency_limit(
    name: Annotated[str, cyclopts.Parameter(help="The name or ID of the work queue")],
    limit: Annotated[
        int, cyclopts.Parameter(help="The concurrency limit to set on the queue.")
    ],
    *,
    pool: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--pool",
            alias="-p",
            help="The name of the work pool that the work queue belongs to.",
        ),
    ] = None,
):
    """Set a concurrency limit on a work queue."""
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    queue_id = await _get_work_queue_id_from_name_or_id(
        name_or_id=name,
        work_pool_name=pool,
    )

    async with get_client() as client:
        try:
            await client.update_work_queue(
                id=queue_id,
                concurrency_limit=limit,
            )
        except ObjectNotFound:
            if pool:
                error_message = (
                    f"No work queue named {name!r} found in work pool {pool!r}."
                )
            else:
                error_message = f"No work queue named {name!r} found."
            exit_with_error(error_message)

    if pool:
        success_message = (
            f"Concurrency limit of {limit} set on work queue {name!r} in work pool"
            f" {pool!r}"
        )
    else:
        success_message = f"Concurrency limit of {limit} set on work queue {name!r}"
    exit_with_success(success_message)


@work_queue_app.command(name="clear-concurrency-limit")
@with_cli_exception_handling
async def clear_concurrency_limit(
    name: Annotated[
        str, cyclopts.Parameter(help="The name or ID of the work queue to clear")
    ],
    *,
    pool: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--pool",
            alias="-p",
            help="The name of the work pool that the work queue belongs to.",
        ),
    ] = None,
):
    """Clear any concurrency limits from a work queue."""
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    queue_id = await _get_work_queue_id_from_name_or_id(
        name_or_id=name,
        work_pool_name=pool,
    )
    async with get_client() as client:
        try:
            await client.update_work_queue(
                id=queue_id,
                concurrency_limit=None,
            )
        except ObjectNotFound:
            if pool:
                error_message = f"No work queue found: {name!r} in work pool {pool!r}"
            else:
                error_message = f"No work queue found: {name!r}"
            exit_with_error(error_message)

    if pool:
        success_message = (
            f"Concurrency limits removed on work queue {name!r} in work pool {pool!r}"
        )
    else:
        success_message = f"Concurrency limits removed on work queue {name!r}"
    exit_with_success(success_message)


@work_queue_app.command(name="pause")
@with_cli_exception_handling
async def pause(
    name: Annotated[
        str, cyclopts.Parameter(help="The name or ID of the work queue to pause")
    ],
    *,
    pool: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--pool",
            alias="-p",
            help="The name of the work pool that the work queue belongs to.",
        ),
    ] = None,
):
    """Pause a work queue."""
    from prefect.cli._prompts import confirm
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.objects import DEFAULT_AGENT_WORK_POOL_NAME
    from prefect.exceptions import ObjectNotFound

    if not pool:
        try:
            confirmed = confirm(
                f"You have not specified a work pool. Are you sure you want to pause {name} work queue in `{DEFAULT_AGENT_WORK_POOL_NAME}`?",
                console=_cli.console,
            )
        except EOFError:
            confirmed = False
        if not confirmed:
            exit_with_error("Work queue pause aborted!")

    queue_id = await _get_work_queue_id_from_name_or_id(
        name_or_id=name,
        work_pool_name=pool,
    )

    async with get_client() as client:
        try:
            await client.update_work_queue(
                id=queue_id,
                is_paused=True,
            )
        except ObjectNotFound:
            if pool:
                error_message = f"No work queue found: {name!r} in work pool {pool!r}"
            else:
                error_message = f"No work queue found: {name!r}"
            exit_with_error(error_message)

    if pool:
        success_message = f"Work queue {name!r} in work pool {pool!r} paused"
    else:
        success_message = f"Work queue {name!r} paused"
    exit_with_success(success_message)


@work_queue_app.command(name="resume")
@with_cli_exception_handling
async def resume(
    name: Annotated[
        str, cyclopts.Parameter(help="The name or ID of the work queue to resume")
    ],
    *,
    pool: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--pool",
            alias="-p",
            help="The name of the work pool that the work queue belongs to.",
        ),
    ] = None,
):
    """Resume a paused work queue."""
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    queue_id = await _get_work_queue_id_from_name_or_id(
        name_or_id=name,
        work_pool_name=pool,
    )

    async with get_client() as client:
        try:
            await client.update_work_queue(
                id=queue_id,
                is_paused=False,
            )
        except ObjectNotFound:
            if pool:
                error_message = f"No work queue found: {name!r} in work pool {pool!r}"
            else:
                error_message = f"No work queue found: {name!r}"
            exit_with_error(error_message)

    if pool:
        success_message = f"Work queue {name!r} in work pool {pool!r} resumed"
    else:
        success_message = f"Work queue {name!r} resumed"
    exit_with_success(success_message)


@work_queue_app.command(name="inspect")
@with_cli_exception_handling
async def inspect(
    name: Annotated[
        str,
        cyclopts.Parameter(help="The name or ID of the work queue to inspect"),
    ],
    *,
    pool: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--pool",
            alias="-p",
            help="The name of the work pool that the work queue belongs to.",
        ),
    ] = None,
    output: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--output",
            alias="-o",
            help="Specify an output format. Currently supports: json",
        ),
    ] = None,
):
    """Inspect a work queue by ID."""
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    queue_id = await _get_work_queue_id_from_name_or_id(
        name_or_id=name,
        work_pool_name=pool,
    )
    async with get_client() as client:
        try:
            result = await client.read_work_queue(id=queue_id)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=DeprecationWarning)

                if output and output.lower() == "json":
                    result_json = result.model_dump(mode="json")

                    try:
                        status = await client.read_work_queue_status(id=queue_id)
                        status_json = status.model_dump(mode="json")
                        result_json["status_details"] = status_json
                    except ObjectNotFound:
                        pass

                    json_output = orjson.dumps(
                        result_json, option=orjson.OPT_INDENT_2
                    ).decode()
                    _cli.console.print(json_output)
                else:
                    _cli.console.print(Pretty(result))
        except ObjectNotFound:
            if pool:
                error_message = f"No work queue found: {name!r} in work pool {pool!r}"
            else:
                error_message = f"No work queue found: {name!r}"
            exit_with_error(error_message)

        if not (output and output.lower() == "json"):
            try:
                status = await client.read_work_queue_status(id=queue_id)
                _cli.console.print(Pretty(status))
            except ObjectNotFound:
                pass


@work_queue_app.command(name="ls")
@with_cli_exception_handling
async def ls(
    *,
    verbose: Annotated[
        bool,
        cyclopts.Parameter("--verbose", alias="-v", help="Display more information."),
    ] = False,
    work_queue_prefix: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--match",
            alias="-m",
            help="Will match work queues with names that start with the specified prefix string",
        ),
    ] = None,
    pool: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--pool",
            alias="-p",
            help="The name of the work pool containing the work queues to list.",
        ),
    ] = None,
):
    """View all work queues."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import WorkPoolFilter, WorkPoolFilterId
    from prefect.client.schemas.objects import WorkQueue
    from prefect.exceptions import ObjectNotFound
    from prefect.types._datetime import now as now_fn

    if not pool:
        table = Table(
            title="Work Queues",
            caption="(**) denotes a paused queue",
            caption_style="red",
        )
        table.add_column("Name", style="green", no_wrap=True)
        table.add_column("Pool", style="magenta", no_wrap=True)
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Concurrency Limit", style="blue", no_wrap=True)
        if verbose:
            table.add_column("Filter (Deprecated)", style="magenta", no_wrap=True)

        async with get_client() as client:
            if work_queue_prefix is not None:
                queues = await client.match_work_queues([work_queue_prefix])
            else:
                queues = await client.read_work_queues()

            pool_ids = [q.work_pool_id for q in queues]
            wp_filter = WorkPoolFilter(id=WorkPoolFilterId(any_=pool_ids))
            pools = await client.read_work_pools(work_pool_filter=wp_filter)
            pool_id_name_map = {p.id: p.name for p in pools}

            def sort_by_created_key(q: WorkQueue):
                assert q.created is not None, "created is not None"
                return now_fn("UTC") - q.created

            for queue in sorted(queues, key=sort_by_created_key):
                row = [
                    f"{queue.name} [red](**)" if queue.is_paused else queue.name,
                    pool_id_name_map[queue.work_pool_id],
                    str(queue.id),
                    (
                        f"[red]{queue.concurrency_limit}"
                        if queue.concurrency_limit is not None
                        else "[blue]None"
                    ),
                ]
                if verbose and queue.filter is not None:
                    row.append(queue.filter.model_dump_json())
                table.add_row(*row)

    else:
        table = Table(
            title=f"Work Queues in Work Pool {pool!r}",
            caption="(**) denotes a paused queue",
            caption_style="red",
        )
        table.add_column("Name", style="green", no_wrap=True)
        table.add_column("Priority", style="magenta", no_wrap=True)
        table.add_column("Concurrency Limit", style="blue", no_wrap=True)
        if verbose:
            table.add_column("Description", style="cyan", no_wrap=False)

        async with get_client() as client:
            try:
                queues = await client.read_work_queues(work_pool_name=pool)
            except ObjectNotFound:
                exit_with_error(f"No work pool found: {pool!r}")

            def sort_by_created_key(q: WorkQueue):
                assert q.created is not None, "created is not None"
                return now_fn("UTC") - q.created

            for queue in sorted(queues, key=sort_by_created_key):
                row = [
                    f"{queue.name} [red](**)" if queue.is_paused else queue.name,
                    f"{queue.priority}",
                    (
                        f"[red]{queue.concurrency_limit}"
                        if queue.concurrency_limit is not None
                        else "[blue]None"
                    ),
                ]
                if verbose:
                    row.append(queue.description)
                table.add_row(*row)

    _cli.console.print(table)


@work_queue_app.command(name="preview")
@with_cli_exception_handling
async def preview(
    name: Annotated[
        str,
        cyclopts.Parameter(help="The name or ID of the work queue to preview"),
    ],
    *,
    hours: Annotated[
        Optional[int],
        cyclopts.Parameter(
            "--hours",
            alias="-h",
            help="The number of hours to look ahead; defaults to 1 hour",
        ),
    ] = None,
    pool: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--pool",
            alias="-p",
            help="The name of the work pool that the work queue belongs to.",
        ),
    ] = None,
):
    """Preview a work queue."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.objects import FlowRun
    from prefect.exceptions import ObjectNotFound
    from prefect.types._datetime import now as now_fn

    if pool:
        title = f"Preview of Work Queue {name!r} in Work Pool {pool!r}"
    else:
        title = f"Preview of Work Queue {name!r}"

    table = Table(title=title, caption="(**) denotes a late run", caption_style="red")
    table.add_column(
        "Scheduled Start Time", justify="left", style="yellow", no_wrap=True
    )
    table.add_column("Run ID", justify="left", style="cyan", no_wrap=True)
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("Deployment ID", style="blue", no_wrap=True)

    window = now_fn("UTC") + datetime.timedelta(hours=hours or 1)

    queue_id = await _get_work_queue_id_from_name_or_id(
        name_or_id=name, work_pool_name=pool
    )
    async with get_client() as client:
        if pool:
            try:
                responses = await client.get_scheduled_flow_runs_for_work_pool(
                    work_pool_name=pool,
                    work_queue_names=[name],
                )
                runs = [response.flow_run for response in responses]
            except ObjectNotFound:
                exit_with_error(f"No work queue found: {name!r} in work pool {pool!r}")
        else:
            try:
                runs = await client.get_runs_in_work_queue(
                    queue_id,
                    limit=10,
                    scheduled_before=window,
                )
            except ObjectNotFound:
                exit_with_error(f"No work queue found: {name!r}")
    now = now_fn("UTC")

    def sort_by_created_key(r: FlowRun):
        assert r.created is not None, "created is not None"
        return now - r.created

    for run in sorted(runs, key=sort_by_created_key):
        table.add_row(
            (
                f"{run.expected_start_time} [red](**)"
                if run.expected_start_time < now
                else f"{run.expected_start_time}"
            ),
            str(run.id),
            run.name,
            str(run.deployment_id),
        )

    if runs:
        _cli.console.print(table)
    else:
        _cli.console.print(
            (
                "No runs found - try increasing how far into the future you preview"
                " with the --hours flag"
            ),
            style="yellow",
        )


@work_queue_app.command(name="delete")
@with_cli_exception_handling
async def delete(
    name: Annotated[
        str, cyclopts.Parameter(help="The name or ID of the work queue to delete")
    ],
    *,
    pool: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--pool",
            alias="-p",
            help="The name of the work pool containing the work queue to delete.",
        ),
    ] = None,
):
    """Delete a work queue by ID."""
    from prefect.cli._prompts import confirm
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    queue_id = await _get_work_queue_id_from_name_or_id(
        name_or_id=name,
        work_pool_name=pool,
    )
    async with get_client() as client:
        try:
            if _cli.is_interactive() and not confirm(
                f"Are you sure you want to delete work queue with name {name!r}?",
                default=False,
                console=_cli.console,
            ):
                exit_with_error("Deletion aborted.")
            await client.delete_work_queue_by_id(id=queue_id)
        except ObjectNotFound:
            if pool:
                error_message = f"No work queue found: {name!r} in work pool {pool!r}"
            else:
                error_message = f"No work queue found: {name!r}"
            exit_with_error(error_message)
    if pool:
        success_message = (
            f"Successfully deleted work queue {name!r} in work pool {pool!r}"
        )
    else:
        success_message = f"Successfully deleted work queue {name!r}"
    exit_with_success(success_message)


@work_queue_app.command(name="read-runs")
@with_cli_exception_handling
async def read_wq_runs(
    name: Annotated[
        str, cyclopts.Parameter(help="The name or ID of the work queue to poll")
    ],
    *,
    pool: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--pool",
            alias="-p",
            help="The name of the work pool containing the work queue to poll.",
        ),
    ] = None,
):
    """Get runs in a work queue.

    Note that this will trigger an artificial poll of the work queue.
    """
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    queue_id = await _get_work_queue_id_from_name_or_id(
        name_or_id=name,
        work_pool_name=pool,
    )
    async with get_client() as client:
        try:
            runs = await client.get_runs_in_work_queue(id=queue_id)
        except ObjectNotFound:
            if pool:
                error_message = f"No work queue found: {name!r} in work pool {pool!r}"
            else:
                error_message = f"No work queue found: {name!r}"
            exit_with_error(error_message)
    success_message = (
        f"Read {len(runs)} runs for work queue {name!r} in work pool {pool}: {runs}"
    )
    exit_with_success(success_message)
