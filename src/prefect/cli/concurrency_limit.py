"""
Command line interface for working with concurrency limits.
"""

import textwrap

import typer
from rich.console import Group
from rich.panel import Panel
from rich.pretty import Pretty
from rich.table import Table

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app, is_interactive
from prefect.client.orchestration import get_client
from prefect.exceptions import ObjectNotFound
from prefect.types._datetime import human_friendly_diff

concurrency_limit_app: PrefectTyper = PrefectTyper(
    name="concurrency-limit",
    help="Manage task-level concurrency limits.",
)
app.add_typer(concurrency_limit_app, aliases=["concurrency-limits"])


@concurrency_limit_app.command()
async def create(tag: str, concurrency_limit: int):
    """
    Create a concurrency limit against a tag.

    This limit controls how many task runs with that tag may simultaneously be in a
    Running state.
    """

    async with get_client() as client:
        await client.create_concurrency_limit(
            tag=tag, concurrency_limit=concurrency_limit
        )
        await client.read_concurrency_limit_by_tag(tag)

    app.console.print(
        textwrap.dedent(
            f"""
            Created concurrency limit with properties:
                tag - {tag!r}
                concurrency_limit - {concurrency_limit}

            Delete the concurrency limit:
                prefect concurrency-limit delete {tag!r}
            
            Inspect the concurrency limit:
                prefect concurrency-limit inspect {tag!r}
        """
        )
    )


@concurrency_limit_app.command()
async def inspect(tag: str):
    """
    View details about a concurrency limit. `active_slots` shows a list of TaskRun IDs
    which are currently using a concurrency slot.
    """

    async with get_client() as client:
        try:
            result = await client.read_concurrency_limit_by_tag(tag=tag)
        except ObjectNotFound:
            exit_with_error(f"No concurrency limit found for the tag: {tag}")

    trid_table = Table()
    trid_table.add_column("Active Task Run IDs", style="cyan", no_wrap=True)

    cl_table = Table(title=f"Concurrency Limit ID: [red]{str(result.id)}")
    cl_table.add_column("Tag", style="green", no_wrap=True)
    cl_table.add_column("Concurrency Limit", style="blue", no_wrap=True)
    cl_table.add_column("Created", style="magenta", no_wrap=True)
    cl_table.add_column("Updated", style="magenta", no_wrap=True)

    for trid in sorted(result.active_slots):
        trid_table.add_row(str(trid))

    cl_table.add_row(
        str(result.tag),
        str(result.concurrency_limit),
        Pretty(human_friendly_diff(result.created) if result.created else ""),
        Pretty(human_friendly_diff(result.updated) if result.updated else ""),
    )

    group = Group(
        cl_table,
        trid_table,
    )
    app.console.print(Panel(group, expand=False))


@concurrency_limit_app.command()
async def ls(limit: int = 15, offset: int = 0):
    """
    View all concurrency limits.
    """
    table = Table(
        title="Concurrency Limits",
        caption="inspect a concurrency limit to show active task run IDs",
    )
    table.add_column("Tag", style="green", no_wrap=True)
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Concurrency Limit", style="blue", no_wrap=True)
    table.add_column("Active Task Runs", style="magenta", no_wrap=True)

    async with get_client() as client:
        concurrency_limits = await client.read_concurrency_limits(
            limit=limit, offset=offset
        )

    for cl in sorted(
        concurrency_limits, key=lambda c: c.updated or c.created or "", reverse=True
    ):
        table.add_row(
            str(cl.tag),
            str(cl.id),
            str(cl.concurrency_limit),
            str(len(cl.active_slots)),
        )

    app.console.print(table)


@concurrency_limit_app.command()
async def reset(tag: str):
    """
    Resets the concurrency limit slots set on the specified tag.
    """

    async with get_client() as client:
        try:
            await client.reset_concurrency_limit_by_tag(tag=tag)
        except ObjectNotFound:
            exit_with_error(f"No concurrency limit found for the tag: {tag}")

    exit_with_success(f"Reset concurrency limit set on the tag: {tag}")


@concurrency_limit_app.command()
async def delete(tag: str):
    """
    Delete the concurrency limit set on the specified tag.
    """

    async with get_client() as client:
        try:
            if is_interactive() and not typer.confirm(
                (
                    f"Are you sure you want to delete concurrency limit with tag {tag!r}?"
                ),
                default=False,
            ):
                exit_with_error("Deletion aborted.")
            await client.delete_concurrency_limit_by_tag(tag=tag)
        except ObjectNotFound:
            exit_with_error(f"No concurrency limit found for the tag: {tag}")

    exit_with_success(f"Deleted concurrency limit set on the tag: {tag}")
