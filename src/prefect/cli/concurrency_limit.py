"""
Command line interface for working with concurrency limits.
"""
import textwrap

import pendulum

try:
    from rich.console import Group
except ImportError:
    # Name changed in https://github.com/Textualize/rich/blob/master/CHANGELOG.md#1100---2022-01-09
    from rich.console import RenderGroup as Group

from rich.panel import Panel
from rich.pretty import Pretty
from rich.table import Table

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client import get_client
from prefect.exceptions import ObjectNotFound

concurrency_limit_app = PrefectTyper(
    name="concurrency-limit",
    help="Commands for managing task-level concurrency limits.",
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
        result = await client.read_concurrency_limit_by_tag(tag)

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

    for trid in result.active_slots:
        trid_table.add_row(str(trid))

    cl_table.add_row(
        str(result.tag),
        str(result.concurrency_limit),
        Pretty(pendulum.instance(result.created).diff_for_humans()),
        Pretty(pendulum.instance(result.updated).diff_for_humans()),
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

    for cl in sorted(concurrency_limits, key=lambda c: c.updated, reverse=True):
        table.add_row(
            str(cl.tag),
            str(cl.id),
            str(cl.concurrency_limit),
            str(len(cl.active_slots)),
        )

    app.console.print(table)


@concurrency_limit_app.command()
async def delete(tag: str):
    """
    Delete the concurrency limit set on the specified tag.
    """

    async with get_client() as client:
        try:
            await client.delete_concurrency_limit_by_tag(tag=tag)
        except ObjectNotFound:
            exit_with_error(f"No concurrency limit found for the tag: {tag}")

    exit_with_success(f"Deleted concurrency limit set on the tag: {tag}")
