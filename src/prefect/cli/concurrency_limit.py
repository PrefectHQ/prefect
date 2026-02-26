"""
Concurrency-limit command — native cyclopts implementation.

Manage task-level concurrency limits.
"""

import textwrap
from typing import Annotated, Optional

import cyclopts
from rich.console import Group
from rich.panel import Panel
from rich.pretty import Pretty
from rich.table import Table

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

concurrency_limit_app: cyclopts.App = cyclopts.App(
    name="concurrency-limit",
    alias="concurrency-limits",
    help="Manage task-level concurrency limits.",
    version_flags=[],
    help_flags=["--help"],
)


@concurrency_limit_app.command()
@with_cli_exception_handling
async def create(tag: str, concurrency_limit: int):
    """Create a concurrency limit against a tag."""
    from prefect.client.orchestration import get_client

    async with get_client() as client:
        await client.create_concurrency_limit(
            tag=tag, concurrency_limit=concurrency_limit
        )
        await client.read_concurrency_limit_by_tag(tag)

    _cli.console.print(
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
@with_cli_exception_handling
async def inspect(
    tag: str,
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
    """View details about a concurrency limit."""
    import orjson

    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound
    from prefect.types._datetime import human_friendly_diff

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    async with get_client() as client:
        try:
            result = await client.read_concurrency_limit_by_tag(tag=tag)
        except ObjectNotFound:
            exit_with_error(f"No concurrency limit found for the tag: {tag}")

    if output and output.lower() == "json":
        result_json = result.model_dump(mode="json")
        json_output = orjson.dumps(result_json, option=orjson.OPT_INDENT_2).decode()
        _cli.console.print(json_output)
    else:
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
        _cli.console.print(Panel(group, expand=False))


@concurrency_limit_app.command()
@with_cli_exception_handling
async def ls(
    *,
    limit: Annotated[
        int,
        cyclopts.Parameter("--limit", help="Maximum number of limits to list."),
    ] = 15,
    offset: Annotated[
        int,
        cyclopts.Parameter("--offset", help="Offset for pagination."),
    ] = 0,
):
    """View all concurrency limits."""
    from prefect.client.orchestration import get_client

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

    _cli.console.print(table)


@concurrency_limit_app.command()
@with_cli_exception_handling
async def reset(tag: str):
    """Resets the concurrency limit slots set on the specified tag."""
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    async with get_client() as client:
        try:
            await client.reset_concurrency_limit_by_tag(tag=tag)
        except ObjectNotFound:
            exit_with_error(f"No concurrency limit found for the tag: {tag}")

    exit_with_success(f"Reset concurrency limit set on the tag: {tag}")


@concurrency_limit_app.command()
@with_cli_exception_handling
async def delete(tag: str):
    """Delete the concurrency limit set on the specified tag."""
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    async with get_client() as client:
        try:
            if _cli.is_interactive():
                from prefect.cli._prompts import confirm

                if not confirm(
                    f"Are you sure you want to delete concurrency limit with tag {tag!r}?",
                    default=False,
                    console=_cli.console,
                ):
                    exit_with_error("Deletion aborted.")
            await client.delete_concurrency_limit_by_tag(tag=tag)
        except ObjectNotFound:
            exit_with_error(f"No concurrency limit found for the tag: {tag}")

    exit_with_success(f"Deleted concurrency limit set on the tag: {tag}")
