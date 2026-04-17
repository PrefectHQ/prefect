"""
Work pool command — native cyclopts implementation.

Manage work pools.
"""

from __future__ import annotations

import datetime
import json
import textwrap
from typing import Annotated, Any, Optional

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

work_pool_app: cyclopts.App = cyclopts.App(
    name="work-pool",
    alias="work-pools",
    help="Manage work pools.",
    version_flags=[],
    help_flags=["--help"],
)

# --- storage subapp ---
work_pool_storage_app: cyclopts.App = cyclopts.App(
    name="storage",
    help="EXPERIMENTAL: Manage work pool storage.",
    version_flags=[],
    help_flags=["--help"],
)
work_pool_app.command(work_pool_storage_app)

# --- storage configure sub-subapp ---
work_pool_storage_configure_app: cyclopts.App = cyclopts.App(
    name="configure",
    help="EXPERIMENTAL: Configure work pool storage.",
    version_flags=[],
    help_flags=["--help"],
)
work_pool_storage_app.command(work_pool_storage_configure_app)

_LAUNCHER_GROUP = cyclopts.Group(
    "Launchers",
    help=(
        "Example: use Python for upload and execution:"
        " --launcher python --launcher-arg -X --launcher-arg utf8"
    ),
)

_LAUNCHER_HELP = "Shared executable or path for upload and execution."
_LAUNCHER_ARG_HELP = "Append one argv token to the shared launcher. Repeat per token."
_UPLOAD_LAUNCHER_HELP = "Replace the shared executable or path for upload only."
_UPLOAD_LAUNCHER_ARG_HELP = (
    "Append one upload-only argv token. Extends the shared launcher."
)
_EXECUTION_LAUNCHER_HELP = "Replace the shared executable or path for execution only."
_EXECUTION_LAUNCHER_ARG_HELP = (
    "Append one execution-only argv token. Extends the shared launcher."
)
LauncherOption = Annotated[
    Optional[str],
    cyclopts.Parameter(
        "--launcher",
        help=_LAUNCHER_HELP,
        group=_LAUNCHER_GROUP,
    ),
]
LauncherArgOption = Annotated[
    Optional[list[str]],
    cyclopts.Parameter(
        "--launcher-arg",
        help=_LAUNCHER_ARG_HELP,
        allow_leading_hyphen=True,
        group=_LAUNCHER_GROUP,
        negative_iterable="",
    ),
]
UploadLauncherOption = Annotated[
    Optional[str],
    cyclopts.Parameter(
        "--upload-launcher",
        help=_UPLOAD_LAUNCHER_HELP,
        group=_LAUNCHER_GROUP,
    ),
]
UploadLauncherArgOption = Annotated[
    Optional[list[str]],
    cyclopts.Parameter(
        "--upload-launcher-arg",
        help=_UPLOAD_LAUNCHER_ARG_HELP,
        allow_leading_hyphen=True,
        group=_LAUNCHER_GROUP,
        negative_iterable="",
    ),
]
ExecutionLauncherOption = Annotated[
    Optional[str],
    cyclopts.Parameter(
        "--execution-launcher",
        help=_EXECUTION_LAUNCHER_HELP,
        group=_LAUNCHER_GROUP,
    ),
]
ExecutionLauncherArgOption = Annotated[
    Optional[list[str]],
    cyclopts.Parameter(
        "--execution-launcher-arg",
        help=_EXECUTION_LAUNCHER_ARG_HELP,
        allow_leading_hyphen=True,
        group=_LAUNCHER_GROUP,
        negative_iterable="",
    ),
]


def _format_duration(seconds: float | int | None) -> str:
    """Format seconds as human-readable duration like '2m 5s' or '1h 2m'."""
    if seconds is None:
        return "N/A"
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m"


def _build_launcher(
    executable: str | None,
    args: list[str] | None,
    *,
    executable_option: str,
) -> list[str] | None:
    if args and any(not arg.strip() for arg in args):
        exit_with_error(f"{executable_option}-arg cannot be empty.")
    if executable is None:
        if args:
            exit_with_error(f"{executable_option}-arg requires {executable_option}.")
        return None
    if not executable.strip():
        exit_with_error(f"{executable_option} cannot be empty.")

    return [executable, *(args or [])]


def _resolve_launcher_override(
    default_launcher: list[str] | None,
    override_executable: str | None,
    override_args: list[str] | None,
    *,
    override_option: str,
) -> list[str] | None:
    if override_args and any(not arg.strip() for arg in override_args):
        exit_with_error(f"{override_option}-arg cannot be empty.")
    if override_executable is not None:
        if not override_executable.strip():
            exit_with_error(f"{override_option} cannot be empty.")
        return [override_executable, *(override_args or [])]

    if override_args:
        if default_launcher is None:
            exit_with_error(
                f"{override_option}-arg requires {override_option} or --launcher."
            )
        return [*default_launcher, *override_args]

    return [*default_launcher] if default_launcher is not None else None


def _resolve_launcher_flags(
    launcher: str | None,
    launcher_args: list[str] | None,
    upload_launcher: str | None,
    upload_launcher_args: list[str] | None,
    execution_launcher: str | None,
    execution_launcher_args: list[str] | None,
) -> tuple[list[str] | None, list[str] | None]:
    default_launcher = _build_launcher(
        launcher,
        launcher_args,
        executable_option="--launcher",
    )
    resolved_upload_launcher = _resolve_launcher_override(
        default_launcher,
        upload_launcher,
        upload_launcher_args,
        override_option="--upload-launcher",
    )
    resolved_execution_launcher = _resolve_launcher_override(
        default_launcher,
        execution_launcher,
        execution_launcher_args,
        override_option="--execution-launcher",
    )

    return resolved_upload_launcher, resolved_execution_launcher


def _build_bundle_step(
    function_fqn: str,
    function_args: dict[str, Any],
    requires: str,
    launcher: list[str] | None,
) -> dict[str, dict[str, Any]]:
    resolved_args = dict(function_args)
    if launcher is None:
        resolved_args["requires"] = requires
    else:
        resolved_args["launcher"] = launcher
    return {function_fqn: resolved_args}


def _get_bundle_step_config(
    step: dict[str, dict[str, Any]] | None,
) -> dict[str, Any] | None:
    if step is None:
        return None
    return next(iter(step.values()))


def _concurrency_style(active: int, limit: int | None) -> str:
    """Return a Rich style string based on utilization percentage.

    Green: 0-60%, Yellow: 61-80%, Red: 81-100%, Blue: no limit.
    """
    if limit is None:
        return "blue"
    if limit == 0:
        return "red"
    ratio = active / limit
    if ratio <= 0.6:
        return "green"
    if ratio <= 0.8:
        return "yellow"
    return "red"


def _slots_bar(active: int, limit: int | None, width: int = 20) -> object:
    """Build a Rich progress bar renderable for slot utilization."""
    from rich.progress_bar import ProgressBar
    from rich.text import Text

    if limit is None:
        return Text(f"{active} active (Unlimited)", style="blue")

    style = _concurrency_style(active, limit)
    bar = ProgressBar(
        total=limit,
        completed=min(active, limit),
        width=width,
        complete_style=style,
        finished_style=style,
    )
    label = Text(f" {active} / {limit}", style=style)

    table = Table(show_header=False, box=None, padding=0, expand=False)
    table.add_row(bar, label)
    return table


def _set_work_pool_as_default(name: str) -> None:
    from prefect.settings import update_current_profile

    profile = update_current_profile({"PREFECT_DEFAULT_WORK_POOL_NAME": name})
    _cli.console.print(
        f"Set {name!r} as default work pool for profile {profile.name!r}\n",
        style="green",
    )
    _cli.console.print(
        (
            "To change your default work pool, run:\n\n\t[blue]prefect config set"
            " PREFECT_DEFAULT_WORK_POOL_NAME=<work-pool-name>[/]\n"
        ),
    )


def _has_provisioner_for_type(work_pool_type: str) -> bool:
    from prefect.infrastructure import provisioners

    return work_pool_type in provisioners._provisioners


@work_pool_app.command(name="create")
@with_cli_exception_handling
async def create(
    name: Annotated[str, cyclopts.Parameter(help="The name of the work pool.")],
    *,
    base_job_template: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--base-job-template",
            help=(
                "The path to a JSON file containing the base job template to use."
                " If unspecified, Prefect will use the default base job template"
                " for the given worker type."
            ),
        ),
    ] = None,
    paused: Annotated[
        bool,
        cyclopts.Parameter(
            "--paused",
            help="Whether or not to create the work pool in a paused state.",
        ),
    ] = False,
    type: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--type", alias="-t", help="The type of work pool to create."
        ),
    ] = None,
    set_as_default: Annotated[
        bool,
        cyclopts.Parameter(
            "--set-as-default",
            help=(
                "Whether or not to use the created work pool as the local default"
                " for deployment."
            ),
        ),
    ] = False,
    provision_infrastructure: Annotated[
        bool,
        cyclopts.Parameter(
            "--provision-infrastructure",
            alias="--provision-infra",
            help=(
                "Whether or not to provision infrastructure for the work pool if"
                " supported for the given work pool type."
            ),
        ),
    ] = False,
    overwrite: Annotated[
        bool,
        cyclopts.Parameter(
            "--overwrite",
            help="Whether or not to overwrite an existing work pool with the same name.",
        ),
    ] = False,
):
    """Create a new work pool or update an existing one."""
    from prefect.cli._prompts import prompt_select_from_table
    from prefect.client.collections import get_collections_metadata_client
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolCreate
    from prefect.exceptions import (
        ObjectAlreadyExists,
        ObjectNotFound,
        PrefectHTTPStatusError,
    )
    from prefect.infrastructure import provisioners
    from prefect.utilities import urls
    from prefect.workers.utilities import (
        get_available_work_pool_types,
        get_default_base_job_template_for_infrastructure_type,
    )

    if not name.lower().strip("'\" "):
        exit_with_error("Work pool name cannot be empty.")

    async with get_client() as client:
        try:
            existing_pool = await client.read_work_pool(work_pool_name=name)
            if not overwrite:
                exit_with_error(
                    f"Work pool named {name!r} already exists. Use --overwrite to update it."
                )
        except ObjectNotFound:
            existing_pool = None

        if type is None and existing_pool is None:
            async with get_collections_metadata_client() as collections_client:
                if not _cli.is_interactive():
                    exit_with_error(
                        "When not using an interactive terminal, you must supply a"
                        " `--type` value."
                    )
                worker_metadata = await collections_client.read_worker_metadata()

                data = [
                    worker
                    for collection in worker_metadata.values()
                    for worker in collection.values()
                    if provision_infrastructure
                    and _has_provisioner_for_type(worker["type"])
                    or not provision_infrastructure
                ]
                worker = prompt_select_from_table(
                    _cli.console,
                    "What type of work pool infrastructure would you like to use?",
                    columns=[
                        {"header": "Infrastructure Type", "key": "display_name"},
                        {"header": "Description", "key": "description"},
                    ],
                    data=data,
                    table_kwargs={"show_lines": True},
                )
                type = worker["type"]
        elif existing_pool:
            type = existing_pool.type

        available_work_pool_types = await get_available_work_pool_types()
        if type not in available_work_pool_types:
            exit_with_error(
                f"Unknown work pool type {type!r}. "
                "Please choose from"
                f" {', '.join(available_work_pool_types)}."
            )

        if base_job_template is None:
            template_contents = (
                await get_default_base_job_template_for_infrastructure_type(type)
            )
        else:
            with open(base_job_template) as f:
                template_contents = json.load(f)

        if provision_infrastructure:
            try:
                provisioner = (
                    provisioners.get_infrastructure_provisioner_for_work_pool_type(type)
                )
                provisioner.console = _cli.console
                template_contents = await provisioner.provision(
                    work_pool_name=name, base_job_template=template_contents
                )
            except ValueError as exc:
                print(exc)
                _cli.console.print(
                    (
                        "Automatic infrastructure provisioning is not supported for"
                        f" {type!r} work pools."
                    ),
                    style="yellow",
                )
            except RuntimeError as exc:
                exit_with_error(f"Failed to provision infrastructure: {exc}")

        try:
            wp = WorkPoolCreate(
                name=name,
                type=type,
                base_job_template=template_contents,
                is_paused=paused,
            )
            work_pool = await client.create_work_pool(work_pool=wp, overwrite=overwrite)
            action = "Updated" if overwrite and existing_pool else "Created"
            _cli.console.print(
                f"{action} work pool {work_pool.name!r}!\n", style="green"
            )
            if (
                not work_pool.is_paused
                and not work_pool.is_managed_pool
                and not work_pool.is_push_pool
            ):
                _cli.console.print("To start a worker for this work pool, run:\n")
                _cli.console.print(
                    f"\t[blue]prefect worker start --pool {work_pool.name}[/]\n"
                )
            if set_as_default:
                _set_work_pool_as_default(work_pool.name)

            url = urls.url_for(work_pool)
            pool_url = url if url else "<no dashboard available>"

            _cli.console.print(
                textwrap.dedent(
                    f"""
                └── UUID: {work_pool.id}
                └── Type: {work_pool.type}
                └── Description: {work_pool.description}
                └── Status: {work_pool.status.display_name}
                └── URL: {pool_url}
                """
                ).strip(),
                soft_wrap=True,
            )
            exit_with_success("")
        except ObjectAlreadyExists:
            exit_with_error(
                f"Work pool named {name!r} already exists. Please use --overwrite to update it."
            )
        except PrefectHTTPStatusError as exc:
            detail = exc.response.json().get("detail")
            if detail:
                exit_with_error(detail)
            else:
                raise


@work_pool_app.command(name="ls")
@with_cli_exception_handling
async def ls(
    *,
    verbose: Annotated[
        bool,
        cyclopts.Parameter(
            "--verbose",
            alias="-v",
            help="Show additional information about work pools.",
        ),
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
    """List work pools."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.objects import WorkPool
    from prefect.types._datetime import now as now_fn

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    async with get_client() as client:
        pools = await client.read_work_pools()

    def sort_by_created_key(q: WorkPool) -> datetime.timedelta:
        assert q.created is not None
        return now_fn("UTC") - q.created

    sorted_pools = sorted(pools, key=sort_by_created_key)

    if not sorted_pools:
        if output and output.lower() == "json":
            _cli.console.print("[]")
            return
        exit_with_success("No work pools found.")

    if output and output.lower() == "json":
        pools_json = [pool.model_dump(mode="json") for pool in sorted_pools]
        json_output = orjson.dumps(pools_json, option=orjson.OPT_INDENT_2).decode()
        _cli.console.print(json_output, soft_wrap=True)
    else:
        table = Table(
            title="Work Pools",
            caption="(**) denotes a paused pool",
            caption_style="red",
        )
        table.add_column("Name", style="green", no_wrap=True)
        table.add_column("Type", style="magenta", no_wrap=True)
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Concurrency Limit", style="blue", no_wrap=True)
        if verbose:
            table.add_column("Base Job Template", style="magenta", no_wrap=True)

        for pool in sorted_pools:
            row = [
                f"{pool.name} [red](**)" if pool.is_paused else pool.name,
                str(pool.type),
                str(pool.id),
                (
                    f"[red]{pool.concurrency_limit}"
                    if pool.concurrency_limit is not None
                    else "[blue]None"
                ),
            ]
            if verbose:
                row.append(str(pool.base_job_template))
            table.add_row(*row)

        _cli.console.print(table)


@work_pool_app.command(name="inspect")
@with_cli_exception_handling
async def inspect(
    name: Annotated[
        str, cyclopts.Parameter(help="The name of the work pool to inspect.")
    ],
    *,
    output: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--output",
            alias="-o",
            help="Specify an output format. Currently supports: json",
        ),
    ] = None,
):
    """Inspect a work pool."""
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    async with get_client() as client:
        try:
            pool = await client.read_work_pool(work_pool_name=name)
            if output and output.lower() == "json":
                pool_json = pool.model_dump(mode="json")
                json_output = orjson.dumps(
                    pool_json, option=orjson.OPT_INDENT_2
                ).decode()
                _cli.console.print(json_output, soft_wrap=True)
            else:
                _cli.console.print(Pretty(pool))
        except ObjectNotFound:
            exit_with_error(f"Work pool {name!r} not found!")


@work_pool_app.command(name="slots")
@with_cli_exception_handling
async def slots(
    name: Annotated[str, cyclopts.Parameter(help="The name of the work pool.")],
    *,
    output: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--output",
            alias="-o",
            help="Specify an output format. Currently supports: json",
        ),
    ] = None,
):
    """Show concurrency slot utilization for a work pool."""
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    async with get_client() as client:
        try:
            # Fetch all pages of queue data with full flow run details
            status = await client.read_work_pool_concurrency_status(
                work_pool_name=name, flow_run_limit=200
            )
            # Paginate through remaining queue pages
            while (
                status.page is not None
                and status.pages is not None
                and status.page < status.pages
            ):
                next_page = await client.read_work_pool_concurrency_status(
                    work_pool_name=name,
                    page=status.page + 1,
                    flow_run_limit=200,
                )
                status.queues.extend(next_page.queues)
                status.page = next_page.page
            # Reset pagination metadata to reflect the aggregated result
            status.page = 1
            status.pages = 1
            status.count = len(status.queues)
            status.limit = len(status.queues)
        except ObjectNotFound:
            exit_with_error(f"Work pool {name!r} not found!")

    if output and output.lower() == "json":
        data = status.model_dump(mode="json")
        # Flag any queues where flow_runs were truncated by the API limit
        for queue_data in data.get("queues", []):
            total = queue_data.get("flow_run_count") or len(
                queue_data.get("flow_runs", [])
            )
            if total > len(queue_data.get("flow_runs", [])):
                queue_data["_truncated"] = {
                    "shown": len(queue_data["flow_runs"]),
                    "total": total,
                }
        json_output = orjson.dumps(data, option=orjson.OPT_INDENT_2).decode()
        _cli.console.print(json_output, soft_wrap=True)
        return

    # Header
    _cli.console.print(f"\nWork Pool: [green]{name}[/green]")
    _cli.console.print("  Slots: ", end="")
    _cli.console.print(_slots_bar(status.active_slots, status.concurrency_limit))
    _cli.console.print()

    # Collect all flow runs across queues into a single table
    all_runs = []
    truncated_queues = []
    for queue in status.queues:
        for run in queue.flow_runs:
            duration = _format_duration(
                run.time_in_current_state.total_seconds()
                if run.time_in_current_state
                else None
            )
            all_runs.append(
                (queue.queue_name, run.name, run.state_name or "Unknown", duration)
            )
        # Detect truncation: flow_run_count is the true total
        total = queue.flow_run_count or len(queue.flow_runs)
        if total > len(queue.flow_runs):
            truncated_queues.append((queue.queue_name, len(queue.flow_runs), total))

    if not all_runs:
        _cli.console.print("No flow runs occupying slots.", style="dim")
        return

    table = Table(show_header=True, pad_edge=False, box=None)
    table.add_column("Queue", style="cyan", no_wrap=True)
    table.add_column("Flow Run", style="green", no_wrap=True)
    table.add_column("State", style="magenta", no_wrap=True)
    table.add_column("Duration", style="cyan", no_wrap=True)

    for queue_name, run_name, state, duration in all_runs:
        table.add_row(queue_name, run_name, state, duration)

    _cli.console.print(table)

    for q_name, shown, total in truncated_queues:
        _cli.console.print(
            f"\n[yellow]Queue {q_name!r}: showing {shown} of {total} slot holders[/yellow]"
        )


@work_pool_app.command(name="pause")
@with_cli_exception_handling
async def pause(
    name: Annotated[
        str, cyclopts.Parameter(help="The name of the work pool to pause.")
    ],
):
    """Pause a work pool."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolUpdate
    from prefect.exceptions import ObjectNotFound

    async with get_client() as client:
        try:
            await client.update_work_pool(
                work_pool_name=name,
                work_pool=WorkPoolUpdate(is_paused=True),
            )
        except ObjectNotFound as exc:
            exit_with_error(exc)

        exit_with_success(f"Paused work pool {name!r}")


@work_pool_app.command(name="resume")
@with_cli_exception_handling
async def resume(
    name: Annotated[
        str, cyclopts.Parameter(help="The name of the work pool to resume.")
    ],
):
    """Resume a work pool."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolUpdate
    from prefect.exceptions import ObjectNotFound

    async with get_client() as client:
        try:
            await client.update_work_pool(
                work_pool_name=name,
                work_pool=WorkPoolUpdate(is_paused=False),
            )
        except ObjectNotFound as exc:
            exit_with_error(exc)

        exit_with_success(f"Resumed work pool {name!r}")


@work_pool_app.command(name="update")
@with_cli_exception_handling
async def update(
    name: Annotated[
        str, cyclopts.Parameter(help="The name of the work pool to update.")
    ],
    *,
    base_job_template: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--base-job-template",
            help=(
                "The path to a JSON file containing the base job template to use."
                " If None, the base job template will not be modified."
            ),
        ),
    ] = None,
    concurrency_limit: Annotated[
        Optional[int],
        cyclopts.Parameter(
            "--concurrency-limit",
            help=(
                "The concurrency limit for the work pool."
                " If None, the concurrency limit will not be modified."
            ),
        ),
    ] = None,
    description: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--description",
            help=(
                "The description for the work pool."
                " If None, the description will not be modified."
            ),
        ),
    ] = None,
):
    """Update a work pool."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolUpdate
    from prefect.exceptions import ObjectNotFound

    wp = WorkPoolUpdate()
    if base_job_template:
        with open(base_job_template) as f:
            wp.base_job_template = json.load(f)
    if concurrency_limit:
        wp.concurrency_limit = concurrency_limit
    if description:
        wp.description = description

    async with get_client() as client:
        try:
            await client.update_work_pool(
                work_pool_name=name,
                work_pool=wp,
            )
        except ObjectNotFound:
            exit_with_error(f"Work pool named {name!r} does not exist.")

        exit_with_success(f"Updated work pool {name!r}")


@work_pool_app.command(name="provision-infrastructure")
@with_cli_exception_handling
async def provision_infrastructure_cmd(
    name: Annotated[
        str,
        cyclopts.Parameter(
            help="The name of the work pool to provision infrastructure for."
        ),
    ],
):
    """Provision infrastructure for a work pool."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolUpdate
    from prefect.exceptions import ObjectNotFound
    from prefect.infrastructure import provisioners

    async with get_client() as client:
        try:
            work_pool = await client.read_work_pool(work_pool_name=name)
            if not work_pool.is_push_pool:
                exit_with_error(
                    f"Work pool {name!r} is not a push pool type. "
                    "Please try provisioning infrastructure for a push pool."
                )
        except ObjectNotFound:
            exit_with_error(f"Work pool {name!r} does not exist.")
        except Exception as exc:
            exit_with_error(f"Failed to read work pool {name!r}: {exc}")

        try:
            provisioner = (
                provisioners.get_infrastructure_provisioner_for_work_pool_type(
                    work_pool.type
                )
            )
            provisioner.console = _cli.console
            new_base_job_template = await provisioner.provision(
                work_pool_name=name, base_job_template=work_pool.base_job_template
            )

            await client.update_work_pool(
                work_pool_name=name,
                work_pool=WorkPoolUpdate(
                    base_job_template=new_base_job_template,
                ),
            )

        except ValueError as exc:
            _cli.console.print(f"Error: {exc}")
            _cli.console.print(
                (
                    "Automatic infrastructure provisioning is not supported for"
                    f" {work_pool.type!r} work pools."
                ),
                style="yellow",
            )
        except RuntimeError as exc:
            exit_with_error(
                f"Failed to provision infrastructure for '{name}' work pool: {exc}"
            )


# Register alias: provision-infra -> provision-infrastructure
work_pool_app.command(provision_infrastructure_cmd, name="provision-infra")


@work_pool_app.command(name="delete")
@with_cli_exception_handling
async def delete(
    name: Annotated[
        str, cyclopts.Parameter(help="The name of the work pool to delete.")
    ],
):
    """Delete a work pool."""
    from prefect.cli._prompts import confirm
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    async with get_client() as client:
        try:
            work_pool = await client.read_work_pool(work_pool_name=name)
            if _cli.is_interactive() and not confirm(
                f"Are you sure you want to delete work pool with name {work_pool.name!r}?",
                default=False,
                console=_cli.console,
            ):
                exit_with_error("Deletion aborted.")
            await client.delete_work_pool(work_pool_name=name)
        except ObjectNotFound:
            exit_with_error(f"Work pool {name!r} does not exist.")

        exit_with_success(f"Deleted work pool {name!r}")


@work_pool_app.command(name="set-concurrency-limit")
@with_cli_exception_handling
async def set_concurrency_limit(
    name: Annotated[
        str, cyclopts.Parameter(help="The name of the work pool to update.")
    ],
    concurrency_limit: Annotated[
        int, cyclopts.Parameter(help="The new concurrency limit for the work pool.")
    ],
):
    """Set the concurrency limit for a work pool."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolUpdate
    from prefect.exceptions import ObjectNotFound

    async with get_client() as client:
        try:
            await client.update_work_pool(
                work_pool_name=name,
                work_pool=WorkPoolUpdate(concurrency_limit=concurrency_limit),
            )
        except ObjectNotFound as exc:
            exit_with_error(exc)

        exit_with_success(
            f"Set concurrency limit for work pool {name!r} to {concurrency_limit}"
        )


@work_pool_app.command(name="clear-concurrency-limit")
@with_cli_exception_handling
async def clear_concurrency_limit(
    name: Annotated[
        str, cyclopts.Parameter(help="The name of the work pool to update.")
    ],
):
    """Clear the concurrency limit for a work pool."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolUpdate
    from prefect.exceptions import ObjectNotFound

    async with get_client() as client:
        try:
            await client.update_work_pool(
                work_pool_name=name,
                work_pool=WorkPoolUpdate(concurrency_limit=None),
            )
        except ObjectNotFound as exc:
            exit_with_error(exc)

        exit_with_success(f"Cleared concurrency limit for work pool {name!r}")


@work_pool_app.command(name="get-default-base-job-template")
@with_cli_exception_handling
async def get_default_base_job_template(
    *,
    type: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--type",
            alias="-t",
            help="The type of work pool for which to get the default base job template.",
        ),
    ] = None,
    file: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--file",
            alias="-f",
            help="If set, write the output to a file.",
        ),
    ] = None,
):
    """Get the default base job template for a given work pool type."""
    from prefect.workers.utilities import (
        get_available_work_pool_types,
        get_default_base_job_template_for_infrastructure_type,
    )

    base_job_template = await get_default_base_job_template_for_infrastructure_type(
        type
    )
    if base_job_template is None:
        exit_with_error(
            f"Unknown work pool type {type!r}. "
            "Please choose from"
            f" {', '.join(await get_available_work_pool_types())}."
        )

    if file is None:
        print(json.dumps(base_job_template, indent=2))
    else:
        with open(file, mode="w") as f:
            json.dump(base_job_template, fp=f, indent=2)


@work_pool_app.command(name="preview")
@with_cli_exception_handling
async def preview(
    name: Annotated[
        Optional[str],
        cyclopts.Parameter(help="The name or ID of the work pool to preview"),
    ] = None,
    *,
    hours: Annotated[
        Optional[int],
        cyclopts.Parameter(
            "--hours",
            alias="-h",
            help="The number of hours to look ahead; defaults to 1 hour",
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
    """Preview the work pool's scheduled work for all queues."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.objects import FlowRun
    from prefect.exceptions import ObjectNotFound
    from prefect.types._datetime import now as now_fn

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    if hours is None:
        hours = 1

    async with get_client() as client:
        try:
            responses = await client.get_scheduled_flow_runs_for_work_pool(
                work_pool_name=name,
            )
        except ObjectNotFound as exc:
            exit_with_error(exc)

    runs = [response.flow_run for response in responses]
    table = Table(caption="(**) denotes a late run", caption_style="red")

    table.add_column(
        "Scheduled Start Time", justify="left", style="yellow", no_wrap=True
    )
    table.add_column("Run ID", justify="left", style="cyan", no_wrap=True)
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("Deployment ID", style="blue", no_wrap=True)

    now = now_fn("UTC")

    def sort_by_created_key(r: FlowRun) -> datetime.timedelta:
        assert r.created is not None
        return now - r.created

    sorted_runs = sorted(runs, key=sort_by_created_key)

    if output and output.lower() == "json":
        runs_json = [run.model_dump(mode="json") for run in sorted_runs]
        json_output = orjson.dumps(runs_json, option=orjson.OPT_INDENT_2).decode()
        _cli.console.print(json_output, soft_wrap=True)
        return

    for run in sorted_runs:
        table.add_row(
            (
                f"{run.expected_start_time} [red](**)"
                if run.expected_start_time and run.expected_start_time < now
                else f"{run.expected_start_time}"
            ),
            str(run.id),
            run.name,
            str(run.deployment_id),
        )

    if sorted_runs:
        _cli.console.print(table)
    else:
        _cli.console.print(
            (
                "No runs found - try increasing how far into the future you preview"
                " with the --hours flag"
            ),
            style="yellow",
        )


# --------------------------------------------------------------------------
# Work Pool Storage Configuration
# --------------------------------------------------------------------------


def _determine_storage_type(
    storage_config: Any,
) -> str | None:
    bundle_steps = [
        storage_config.bundle_upload_step,
        storage_config.bundle_execution_step,
    ]
    if all(step is None for step in bundle_steps):
        return None
    if any(
        step and any("prefect_aws" in function_fqn for function_fqn in step)
        for step in bundle_steps
    ):
        return "S3"
    if any(
        step and any("prefect_gcp" in function_fqn for function_fqn in step)
        for step in bundle_steps
    ):
        return "GCS"
    if any(
        step and any("prefect_azure" in function_fqn for function_fqn in step)
        for step in bundle_steps
    ):
        return "Azure Blob Storage"
    return "Unknown"


@work_pool_storage_app.command(name="inspect")
@with_cli_exception_handling
async def storage_inspect(
    work_pool_name: Annotated[
        str,
        cyclopts.Parameter(
            help="The name of the work pool to display storage configuration for."
        ),
    ],
    *,
    output: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--output",
            alias="-o",
            help="Specify an output format. Currently supports: json",
        ),
    ] = None,
):
    """EXPERIMENTAL: Inspect the storage configuration for a work pool."""
    from rich.panel import Panel

    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    async with get_client() as client:
        try:
            work_pool = await client.read_work_pool(work_pool_name=work_pool_name)

            storage_table = Table(show_header=True, header_style="bold")
            storage_table.add_column("Setting", style="cyan")
            storage_table.add_column("Value")

            storage_type = _determine_storage_type(work_pool.storage_configuration)
            if not storage_type:
                if output and output.lower() == "json":
                    _cli.console.print("{}")
                else:
                    _cli.console.print(
                        f"No storage configuration found for work pool {work_pool_name!r}",
                        style="yellow",
                    )
                return

            if output and output.lower() == "json":
                storage_data: dict[str, Any] = {"type": storage_type}
                upload_config = _get_bundle_step_config(
                    work_pool.storage_configuration.bundle_upload_step
                )
                execution_config = _get_bundle_step_config(
                    work_pool.storage_configuration.bundle_execution_step
                )
                if upload_config is not None:
                    storage_data["upload"] = upload_config
                if execution_config is not None:
                    storage_data["execution"] = execution_config

                json_output = orjson.dumps(
                    storage_data, option=orjson.OPT_INDENT_2
                ).decode()
                _cli.console.print(json_output, soft_wrap=True)
            else:
                storage_table.add_row("type", storage_type)
                upload_config = _get_bundle_step_config(
                    work_pool.storage_configuration.bundle_upload_step
                )
                execution_config = _get_bundle_step_config(
                    work_pool.storage_configuration.bundle_execution_step
                )

                if upload_config is not None:
                    prefix = (
                        ""
                        if execution_config is None or execution_config == upload_config
                        else "upload."
                    )
                    for key, value in upload_config.items():
                        storage_table.add_row(f"{prefix}{key}", str(value))

                if execution_config is not None and execution_config != upload_config:
                    for key, value in execution_config.items():
                        storage_table.add_row(f"execution.{key}", str(value))

                panel = Panel(
                    storage_table,
                    title=f"[bold]Storage Configuration for {work_pool_name}[/bold]",
                    expand=False,
                )

                _cli.console.print(panel)

        except ObjectNotFound:
            exit_with_error(f"Work pool {work_pool_name!r} does not exist.")


async def _create_or_update_block_document(
    client: Any,
    block_document_name: str,
    block_document_data: dict[str, Any],
    block_type_slug: str,
    missing_block_definition_error: str,
) -> Any:
    from prefect.client.schemas.actions import (
        BlockDocumentCreate,
        BlockDocumentUpdate,
    )
    from prefect.exceptions import ObjectNotFound

    try:
        existing_block_document = await client.read_block_document_by_name(
            name=block_document_name, block_type_slug=block_type_slug
        )
    except ObjectNotFound:
        existing_block_document = None

    if existing_block_document is not None:
        await client.update_block_document(
            block_document_id=existing_block_document.id,
            block_document=BlockDocumentUpdate(
                data=block_document_data,
            ),
        )
        block_document = existing_block_document
    else:
        try:
            block_type = await client.read_block_type_by_slug(slug=block_type_slug)
            block_schema = await client.get_most_recent_block_schema_for_block_type(
                block_type_id=block_type.id
            )
        except ObjectNotFound:
            exit_with_error(missing_block_definition_error)
        else:
            if block_schema is None:
                exit_with_error(missing_block_definition_error)

        block_document = await client.create_block_document(
            block_document=BlockDocumentCreate(
                name=block_document_name,
                block_type_id=block_type.id,
                block_schema_id=block_schema.id,
                data=block_document_data,
            )
        )

    return block_document


@work_pool_storage_configure_app.command(name="s3")
@with_cli_exception_handling
async def storage_configure_s3(
    work_pool_name: Annotated[
        str,
        cyclopts.Parameter(help="The name of the work pool to configure storage for."),
    ],
    *,
    bucket: Annotated[
        Optional[str],
        cyclopts.Parameter("--bucket", help="The name of the S3 bucket to use."),
    ] = None,
    credentials_block_name: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--aws-credentials-block-name",
            help="The name of the AWS credentials block to use.",
        ),
    ] = None,
    launcher: LauncherOption = None,
    launcher_arg: LauncherArgOption = None,
    upload_launcher: UploadLauncherOption = None,
    upload_launcher_arg: UploadLauncherArgOption = None,
    execution_launcher: ExecutionLauncherOption = None,
    execution_launcher_arg: ExecutionLauncherArgOption = None,
):
    """EXPERIMENTAL: Configure AWS S3 storage for a work pool."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolUpdate
    from prefect.client.schemas.objects import WorkPoolStorageConfiguration
    from prefect.exceptions import ObjectNotFound

    if bucket is None:
        if not _cli.is_interactive():
            exit_with_error("--bucket is required in non-interactive mode.")
        bucket = _cli.console.input("Enter the name of the S3 bucket to use: ")

    # In interactive mode, prompt so an operator re-running to tweak another
    # flag doesn't silently swap a configured credentials block for ambient
    # auth. Pressing Enter at the prompt is an explicit opt-in to ambient
    # auth. In non-interactive mode the omitted flag means ambient auth
    # (the IaC / Helm use case).
    if credentials_block_name is None and _cli.is_interactive():
        credentials_block_name = (
            _cli.console.input(
                "Enter the name of the AWS credentials block to use"
                " (press Enter to use default credentials): "
            )
            or None
        )

    resolved_upload_launcher, resolved_execution_launcher = _resolve_launcher_flags(
        launcher,
        launcher_arg,
        upload_launcher,
        upload_launcher_arg,
        execution_launcher,
        execution_launcher_arg,
    )

    async with get_client() as client:
        credentials_block_document = None
        if credentials_block_name is not None:
            try:
                credentials_block_document = await client.read_block_document_by_name(
                    name=credentials_block_name, block_type_slug="aws-credentials"
                )
            except ObjectNotFound:
                exit_with_error(
                    f"AWS credentials block {credentials_block_name!r} does not"
                    " exist. Please create one using"
                    " `prefect block create aws-credentials`, or omit"
                    " --aws-credentials-block-name to use default credentials."
                )

        result_storage_block_document_name = f"default-{work_pool_name}-result-storage"
        # Always set `credentials` explicitly (a $ref for a named block, or
        # an empty dict for ambient auth). Setting it on every run clears any
        # stale credential reference from a prior --aws-credentials-block-name
        # invocation, while the merge-update behavior preserves user-managed
        # fields like `base_folder` that the CLI does not send.
        block_data: dict[str, Any] = {
            "bucket_name": bucket,
            "bucket_folder": "results",
            "credentials": (
                {"$ref": {"block_document_id": credentials_block_document.id}}
                if credentials_block_document is not None
                else {}
            ),
        }

        block_document = await _create_or_update_block_document(
            client=client,
            block_document_name=result_storage_block_document_name,
            block_document_data=block_data,
            block_type_slug="s3-bucket",
            missing_block_definition_error=(
                "S3 bucket block definition does not exist server-side."
                " Please install `prefect-aws` and run"
                " `prefect blocks register -m prefect_aws`."
            ),
        )

        bundle_step_config: dict[str, Any] = {"bucket": bucket}
        if credentials_block_name is not None:
            bundle_step_config["aws_credentials_block_name"] = credentials_block_name

        try:
            await client.update_work_pool(
                work_pool_name=work_pool_name,
                work_pool=WorkPoolUpdate(
                    storage_configuration=WorkPoolStorageConfiguration(
                        bundle_upload_step=_build_bundle_step(
                            "prefect_aws.experimental.bundles.upload",
                            bundle_step_config,
                            "prefect-aws",
                            resolved_upload_launcher,
                        ),
                        bundle_execution_step=_build_bundle_step(
                            "prefect_aws.experimental.bundles.execute",
                            bundle_step_config,
                            "prefect-aws",
                            resolved_execution_launcher,
                        ),
                        default_result_storage_block_id=block_document.id,
                    ),
                ),
            )
        except ObjectNotFound:
            exit_with_error(f"Work pool {work_pool_name!r} does not exist.")

        exit_with_success(f"Configured S3 storage for work pool {work_pool_name!r}")


@work_pool_storage_configure_app.command(name="gcs")
@with_cli_exception_handling
async def storage_configure_gcs(
    work_pool_name: Annotated[
        str,
        cyclopts.Parameter(help="The name of the work pool to configure storage for."),
    ],
    *,
    bucket: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--bucket",
            help="The name of the Google Cloud Storage bucket to use.",
        ),
    ] = None,
    credentials_block_name: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--gcp-credentials-block-name",
            help="The name of the Google Cloud credentials block to use.",
        ),
    ] = None,
    launcher: LauncherOption = None,
    launcher_arg: LauncherArgOption = None,
    upload_launcher: UploadLauncherOption = None,
    upload_launcher_arg: UploadLauncherArgOption = None,
    execution_launcher: ExecutionLauncherOption = None,
    execution_launcher_arg: ExecutionLauncherArgOption = None,
):
    """EXPERIMENTAL: Configure Google Cloud storage for a work pool."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolUpdate
    from prefect.client.schemas.objects import WorkPoolStorageConfiguration
    from prefect.exceptions import ObjectNotFound

    if bucket is None:
        if not _cli.is_interactive():
            exit_with_error("--bucket is required in non-interactive mode.")
        bucket = _cli.console.input(
            "Enter the name of the Google Cloud Storage bucket to use: "
        )

    # In interactive mode, prompt so an operator re-running to tweak another
    # flag doesn't silently swap a configured credentials block for ADC.
    # Pressing Enter at the prompt is an explicit opt-in to ambient auth.
    # In non-interactive mode the omitted flag means ambient auth (the IaC /
    # Helm use case).
    if credentials_block_name is None and _cli.is_interactive():
        credentials_block_name = (
            _cli.console.input(
                "Enter the name of the Google Cloud credentials block to use"
                " (press Enter to use default credentials): "
            )
            or None
        )

    resolved_upload_launcher, resolved_execution_launcher = _resolve_launcher_flags(
        launcher,
        launcher_arg,
        upload_launcher,
        upload_launcher_arg,
        execution_launcher,
        execution_launcher_arg,
    )

    async with get_client() as client:
        credentials_block_document = None
        if credentials_block_name is not None:
            try:
                credentials_block_document = await client.read_block_document_by_name(
                    name=credentials_block_name, block_type_slug="gcp-credentials"
                )
            except ObjectNotFound:
                exit_with_error(
                    f"GCS credentials block {credentials_block_name!r} does not"
                    " exist. Please create one using"
                    " `prefect block create gcp-credentials`, or omit"
                    " --gcp-credentials-block-name to use default credentials."
                )

        result_storage_block_document_name = f"default-{work_pool_name}-result-storage"
        # Always set `gcp_credentials` explicitly (a $ref for a named block,
        # or an empty dict for ambient auth). Setting it on every run clears
        # any stale credential reference from a prior
        # --gcp-credentials-block-name invocation, while the merge-update
        # behavior preserves user-managed fields like `bucket_folder`
        # overrides that the CLI does not send.
        block_data: dict[str, Any] = {
            "bucket": bucket,
            "bucket_folder": "results",
            "gcp_credentials": (
                {"$ref": {"block_document_id": credentials_block_document.id}}
                if credentials_block_document is not None
                else {}
            ),
        }

        block_document = await _create_or_update_block_document(
            client=client,
            block_document_name=result_storage_block_document_name,
            block_document_data=block_data,
            block_type_slug="gcs-bucket",
            missing_block_definition_error=(
                "GCS bucket block definition does not exist server-side."
                " Please install `prefect-gcp` and run"
                " `prefect blocks register -m prefect_gcp`."
            ),
        )

        bundle_step_config: dict[str, Any] = {"bucket": bucket}
        if credentials_block_name is not None:
            bundle_step_config["gcp_credentials_block_name"] = credentials_block_name

        try:
            await client.update_work_pool(
                work_pool_name=work_pool_name,
                work_pool=WorkPoolUpdate(
                    storage_configuration=WorkPoolStorageConfiguration(
                        bundle_upload_step=_build_bundle_step(
                            "prefect_gcp.experimental.bundles.upload",
                            bundle_step_config,
                            "prefect-gcp",
                            resolved_upload_launcher,
                        ),
                        bundle_execution_step=_build_bundle_step(
                            "prefect_gcp.experimental.bundles.execute",
                            bundle_step_config,
                            "prefect-gcp",
                            resolved_execution_launcher,
                        ),
                        default_result_storage_block_id=block_document.id,
                    ),
                ),
            )
        except ObjectNotFound:
            exit_with_error(f"Work pool {work_pool_name!r} does not exist.")

        exit_with_success(f"Configured GCS storage for work pool {work_pool_name!r}")


@work_pool_storage_configure_app.command(name="azure-blob-storage")
@with_cli_exception_handling
async def storage_configure_azure_blob_storage(
    work_pool_name: Annotated[
        str,
        cyclopts.Parameter(help="The name of the work pool to configure storage for."),
    ],
    *,
    container: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--container",
            help="The name of the Azure Blob Storage container to use.",
        ),
    ] = None,
    credentials_block_name: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--azure-blob-storage-credentials-block-name",
            help="The name of the Azure Blob Storage credentials block to use.",
        ),
    ] = None,
    launcher: LauncherOption = None,
    launcher_arg: LauncherArgOption = None,
    upload_launcher: UploadLauncherOption = None,
    upload_launcher_arg: UploadLauncherArgOption = None,
    execution_launcher: ExecutionLauncherOption = None,
    execution_launcher_arg: ExecutionLauncherArgOption = None,
):
    """EXPERIMENTAL: Configure Azure Blob Storage for a work pool."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolUpdate
    from prefect.client.schemas.objects import WorkPoolStorageConfiguration
    from prefect.exceptions import ObjectNotFound

    if container is None:
        if not _cli.is_interactive():
            exit_with_error("--container is required in non-interactive mode.")
        container = _cli.console.input(
            "Enter the name of the Azure Blob Storage container to use: "
        )

    if credentials_block_name is None:
        if not _cli.is_interactive():
            exit_with_error(
                "--azure-blob-storage-credentials-block-name is required"
                " in non-interactive mode."
            )
        credentials_block_name = _cli.console.input(
            "Enter the name of the Azure Blob Storage credentials block to use: "
        )

    resolved_upload_launcher, resolved_execution_launcher = _resolve_launcher_flags(
        launcher,
        launcher_arg,
        upload_launcher,
        upload_launcher_arg,
        execution_launcher,
        execution_launcher_arg,
    )

    async with get_client() as client:
        try:
            credentials_block_document = await client.read_block_document_by_name(
                name=credentials_block_name,
                block_type_slug="azure-blob-storage-credentials",
            )
        except ObjectNotFound:
            exit_with_error(
                f"Azure Blob Storage credentials block {credentials_block_name!r}"
                " does not exist. Please create one using"
                " `prefect block create azure-blob-storage-credentials`."
            )

        result_storage_block_document_name = f"default-{work_pool_name}-result-storage"
        block_data = {
            "container_name": container,
            "credentials": {
                "$ref": {"block_document_id": credentials_block_document.id}
            },
        }

        block_document = await _create_or_update_block_document(
            client=client,
            block_document_name=result_storage_block_document_name,
            block_document_data=block_data,
            block_type_slug="azure-blob-storage-container",
            missing_block_definition_error=(
                "Azure Blob Storage container block definition does not exist"
                " server-side. Please install `prefect-azure[storage]` and run"
                " `prefect blocks register -m prefect_azure`."
            ),
        )

        try:
            await client.update_work_pool(
                work_pool_name=work_pool_name,
                work_pool=WorkPoolUpdate(
                    storage_configuration=WorkPoolStorageConfiguration(
                        bundle_upload_step=_build_bundle_step(
                            "prefect_azure.experimental.bundles.upload",
                            {
                                "container": container,
                                "azure_blob_storage_credentials_block_name": credentials_block_name,
                            },
                            "prefect-azure",
                            resolved_upload_launcher,
                        ),
                        bundle_execution_step=_build_bundle_step(
                            "prefect_azure.experimental.bundles.execute",
                            {
                                "container": container,
                                "azure_blob_storage_credentials_block_name": credentials_block_name,
                            },
                            "prefect-azure",
                            resolved_execution_launcher,
                        ),
                        default_result_storage_block_id=block_document.id,
                    ),
                ),
            )
        except ObjectNotFound:
            exit_with_error(f"Work pool {work_pool_name!r} does not exist.")

        exit_with_success(
            f"Configured Azure Blob Storage for work pool {work_pool_name!r}"
        )
