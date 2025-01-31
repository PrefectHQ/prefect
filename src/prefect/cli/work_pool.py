"""
Command line interface for working with work queues.
"""

import json
import textwrap

import typer
from rich.pretty import Pretty
from rich.table import Table

from prefect.cli._prompts import prompt_select_from_table
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
)
from prefect.cli.root import app, is_interactive
from prefect.client.collections import get_collections_metadata_client
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import WorkPoolCreate, WorkPoolUpdate
from prefect.client.schemas.objects import FlowRun, WorkPool
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound
from prefect.infrastructure.provisioners import (
    _provisioners,
    get_infrastructure_provisioner_for_work_pool_type,
)
from prefect.settings import update_current_profile
from prefect.types._datetime import DateTime, PendulumDuration
from prefect.utilities import urls
from prefect.workers.utilities import (
    get_available_work_pool_types,
    get_default_base_job_template_for_infrastructure_type,
)

work_pool_app: PrefectTyper = PrefectTyper(name="work-pool", help="Manage work pools.")
app.add_typer(work_pool_app, aliases=["work-pool"])


def set_work_pool_as_default(name: str) -> None:
    profile = update_current_profile({"PREFECT_DEFAULT_WORK_POOL_NAME": name})
    app.console.print(
        f"Set {name!r} as default work pool for profile {profile.name!r}\n",
        style="green",
    )
    app.console.print(
        (
            "To change your default work pool, run:\n\n\t[blue]prefect config set"
            " PREFECT_DEFAULT_WORK_POOL_NAME=<work-pool-name>[/]\n"
        ),
    )


def has_provisioner_for_type(work_pool_type: str) -> bool:
    """
    Check if there is a provisioner for the given work pool type.

    Args:
        work_pool_type (str): The type of the work pool.

    Returns:
        bool: True if a provisioner exists for the given type, False otherwise.
    """
    return work_pool_type in _provisioners


@work_pool_app.command()
async def create(
    name: str = typer.Argument(..., help="The name of the work pool."),
    base_job_template: typer.FileText = typer.Option(
        None,
        "--base-job-template",
        help=(
            "The path to a JSON file containing the base job template to use. If"
            " unspecified, Prefect will use the default base job template for the given"
            " worker type."
        ),
    ),
    paused: bool = typer.Option(
        False,
        "--paused",
        help="Whether or not to create the work pool in a paused state.",
    ),
    type: str = typer.Option(
        None, "-t", "--type", help="The type of work pool to create."
    ),
    set_as_default: bool = typer.Option(
        False,
        "--set-as-default",
        help=(
            "Whether or not to use the created work pool as the local default for"
            " deployment."
        ),
    ),
    provision_infrastructure: bool = typer.Option(
        False,
        "--provision-infrastructure",
        "--provision-infra",
        help=(
            "Whether or not to provision infrastructure for the work pool if supported"
            " for the given work pool type."
        ),
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help=("Whether or not to overwrite an existing work pool with the same name."),
    ),
):
    """
    Create a new work pool or update an existing one.

    \b
    Examples:
        \b
        Create a Kubernetes work pool in a paused state:
            \b
            $ prefect work-pool create "my-pool" --type kubernetes --paused
        \b
        Create a Docker work pool with a custom base job template:
            \b
            $ prefect work-pool create "my-pool" --type docker --base-job-template ./base-job-template.json
        \b
        Update an existing work pool:
            \b
            $ prefect work-pool create "existing-pool" --base-job-template ./base-job-template.json --overwrite

    """
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
                if not is_interactive():
                    exit_with_error(
                        "When not using an interactive terminal, you must supply a"
                        " `--type` value."
                    )
                worker_metadata = await collections_client.read_worker_metadata()

                # Retrieve only push pools if provisioning infrastructure
                data = [
                    worker
                    for collection in worker_metadata.values()
                    for worker in collection.values()
                    if provision_infrastructure
                    and has_provisioner_for_type(worker["type"])
                    or not provision_infrastructure
                ]
                worker = prompt_select_from_table(
                    app.console,
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
            template_contents = json.load(base_job_template)

        if provision_infrastructure:
            try:
                provisioner = get_infrastructure_provisioner_for_work_pool_type(type)
                provisioner.console = app.console
                template_contents = await provisioner.provision(
                    work_pool_name=name, base_job_template=template_contents
                )
            except ValueError as exc:
                print(exc)
                app.console.print(
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
            app.console.print(
                f"{action} work pool {work_pool.name!r}!\n", style="green"
            )
            if (
                not work_pool.is_paused
                and not work_pool.is_managed_pool
                and not work_pool.is_push_pool
            ):
                app.console.print("To start a worker for this work pool, run:\n")
                app.console.print(
                    f"\t[blue]prefect worker start --pool {work_pool.name}[/]\n"
                )
            if set_as_default:
                set_work_pool_as_default(work_pool.name)

            url = urls.url_for(work_pool)
            pool_url = url if url else "<no dashboard available>"

            app.console.print(
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


@work_pool_app.command()
async def ls(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show additional information about work pools.",
    ),
):
    """
    List work pools.

    \b
    Examples:
        $ prefect work-pool ls
    """
    table = Table(
        title="Work Pools", caption="(**) denotes a paused pool", caption_style="red"
    )
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("Type", style="magenta", no_wrap=True)
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Concurrency Limit", style="blue", no_wrap=True)
    if verbose:
        table.add_column("Base Job Template", style="magenta", no_wrap=True)

    async with get_client() as client:
        pools = await client.read_work_pools()

    def sort_by_created_key(q: WorkPool) -> PendulumDuration:
        assert q.created is not None
        return DateTime.now("utc") - q.created

    for pool in sorted(pools, key=sort_by_created_key):
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

    app.console.print(table)


@work_pool_app.command()
async def inspect(
    name: str = typer.Argument(..., help="The name of the work pool to inspect."),
):
    """
    Inspect a work pool.

    \b
    Examples:
        $ prefect work-pool inspect "my-pool"

    """
    async with get_client() as client:
        try:
            pool = await client.read_work_pool(work_pool_name=name)
            app.console.print(Pretty(pool))
        except ObjectNotFound:
            exit_with_error(f"Work pool {name!r} not found!")


@work_pool_app.command()
async def pause(
    name: str = typer.Argument(..., help="The name of the work pool to pause."),
):
    """
    Pause a work pool.

    \b
    Examples:
        $ prefect work-pool pause "my-pool"

    """
    async with get_client() as client:
        try:
            await client.update_work_pool(
                work_pool_name=name,
                work_pool=WorkPoolUpdate(
                    is_paused=True,
                ),
            )
        except ObjectNotFound as exc:
            exit_with_error(exc)

        exit_with_success(f"Paused work pool {name!r}")


@work_pool_app.command()
async def resume(
    name: str = typer.Argument(..., help="The name of the work pool to resume."),
):
    """
    Resume a work pool.

    \b
    Examples:
        $ prefect work-pool resume "my-pool"

    """
    async with get_client() as client:
        try:
            await client.update_work_pool(
                work_pool_name=name,
                work_pool=WorkPoolUpdate(
                    is_paused=False,
                ),
            )
        except ObjectNotFound as exc:
            exit_with_error(exc)

        exit_with_success(f"Resumed work pool {name!r}")


@work_pool_app.command()
async def update(
    name: str = typer.Argument(..., help="The name of the work pool to update."),
    base_job_template: typer.FileText = typer.Option(
        None,
        "--base-job-template",
        help=(
            "The path to a JSON file containing the base job template to use. If"
            " unspecified, Prefect will use the default base job template for the given"
            " worker type. If None, the base job template will not be modified."
        ),
    ),
    concurrency_limit: int = typer.Option(
        None,
        "--concurrency-limit",
        help=(
            "The concurrency limit for the work pool. If None, the concurrency limit"
            " will not be modified."
        ),
    ),
    description: str = typer.Option(
        None,
        "--description",
        help=(
            "The description for the work pool. If None, the description will not be"
            " modified."
        ),
    ),
):
    """
    Update a work pool.

    \b
    Examples:
        $ prefect work-pool update "my-pool"

    """
    wp = WorkPoolUpdate()
    if base_job_template:
        wp.base_job_template = json.load(base_job_template)
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


@work_pool_app.command(aliases=["provision-infra"])
async def provision_infrastructure(
    name: str = typer.Argument(
        ..., help="The name of the work pool to provision infrastructure for."
    ),
):
    """
    Provision infrastructure for a work pool.

    \b
    Examples:
        $ prefect work-pool provision-infrastructure "my-pool"

        $ prefect work-pool provision-infra "my-pool"

    """
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
            provisioner = get_infrastructure_provisioner_for_work_pool_type(
                work_pool.type
            )
            provisioner.console = app.console
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
            app.console.print(f"Error: {exc}")
            app.console.print(
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


@work_pool_app.command()
async def delete(
    name: str = typer.Argument(..., help="The name of the work pool to delete."),
):
    """
    Delete a work pool.

    \b
    Examples:
        $ prefect work-pool delete "my-pool"

    """
    async with get_client() as client:
        try:
            work_pool = await client.read_work_pool(work_pool_name=name)
            if is_interactive() and not typer.confirm(
                (
                    f"Are you sure you want to delete work pool with name {work_pool.name!r}?"
                ),
                default=False,
            ):
                exit_with_error("Deletion aborted.")
            await client.delete_work_pool(work_pool_name=name)
        except ObjectNotFound:
            exit_with_error(f"Work pool {name!r} does not exist.")

        exit_with_success(f"Deleted work pool {name!r}")


@work_pool_app.command()
async def set_concurrency_limit(
    name: str = typer.Argument(..., help="The name of the work pool to update."),
    concurrency_limit: int = typer.Argument(
        ..., help="The new concurrency limit for the work pool."
    ),
):
    """
    Set the concurrency limit for a work pool.

    \b
    Examples:
        $ prefect work-pool set-concurrency-limit "my-pool" 10

    """
    async with get_client() as client:
        try:
            await client.update_work_pool(
                work_pool_name=name,
                work_pool=WorkPoolUpdate(
                    concurrency_limit=concurrency_limit,
                ),
            )
        except ObjectNotFound as exc:
            exit_with_error(exc)

        exit_with_success(
            f"Set concurrency limit for work pool {name!r} to {concurrency_limit}"
        )


@work_pool_app.command()
async def clear_concurrency_limit(
    name: str = typer.Argument(..., help="The name of the work pool to update."),
):
    """
    Clear the concurrency limit for a work pool.

    \b
    Examples:
        $ prefect work-pool clear-concurrency-limit "my-pool"

    """
    async with get_client() as client:
        try:
            await client.update_work_pool(
                work_pool_name=name,
                work_pool=WorkPoolUpdate(
                    concurrency_limit=None,
                ),
            )
        except ObjectNotFound as exc:
            exit_with_error(exc)

        exit_with_success(f"Cleared concurrency limit for work pool {name!r}")


@work_pool_app.command()
async def get_default_base_job_template(
    type: str = typer.Option(
        None,
        "-t",
        "--type",
        help="The type of work pool for which to get the default base job template.",
    ),
    file: str = typer.Option(
        None, "-f", "--file", help="If set, write the output to a file."
    ),
):
    """
    Get the default base job template for a given work pool type.

    \b
    Examples:
        $ prefect work-pool get-default-base-job-template --type kubernetes
    """
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


@work_pool_app.command()
async def preview(
    name: str = typer.Argument(None, help="The name or ID of the work pool to preview"),
    hours: int = typer.Option(
        None,
        "-h",
        "--hours",
        help="The number of hours to look ahead; defaults to 1 hour",
    ),
):
    """
    Preview the work pool's scheduled work for all queues.

    \b
    Examples:
        $ prefect work-pool preview "my-pool" --hours 24

    """
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

    DateTime.now("utc").add(hours=hours or 1)

    now = DateTime.now("utc")

    def sort_by_created_key(r: FlowRun) -> PendulumDuration:
        assert r.created is not None
        return now - r.created

    for run in sorted(runs, key=sort_by_created_key):
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

    if runs:
        app.console.print(table)
    else:
        app.console.print(
            (
                "No runs found - try increasing how far into the future you preview"
                " with the --hours flag"
            ),
            style="yellow",
        )
