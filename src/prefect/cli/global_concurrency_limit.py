from enum import Enum
from pathlib import Path
from typing import Optional

import orjson
import pendulum
import typer
from rich.pretty import Pretty
from rich.table import Table

from prefect import get_client
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.exceptions import ObjectNotFound

global_concurrency_limit_app = PrefectTyper(
    name="global-concurrency-limit",
    help="Commands for managing global concurrency limits.",
)

app.add_typer(global_concurrency_limit_app, aliases=["gcl"])


class OutputFormat(Enum):
    JSON = "json"
    YAML = "yaml"


@global_concurrency_limit_app.command("ls")
async def list_global_concurrency_limits():
    """
    List all global concurrency limits.
    """
    async with get_client() as client:
        gcl_limits = await client.read_global_concurrency_limits(limit=100, offset=0)
        if not gcl_limits:
            exit_with_success("No global concurrency limits found.")

    table = Table(
        title="Global Concurrency Limits",
        caption="List Global Concurrency Limits using `prefect global-concurrency-limit ls`",
        show_header=True,
    )

    table.add_column("ID", justify="right", style="cyan", no_wrap=True, overflow="fold")

    table.add_column("Created", style="blue", no_wrap=True)
    table.add_column("Updated", style="blue", no_wrap=True)
    table.add_column("Active", style="blue", no_wrap=True)
    table.add_column("Name", style="blue", no_wrap=True, overflow="fold")
    table.add_column("Limit", style="blue", no_wrap=True)
    table.add_column("Active Slots", style="blue", no_wrap=True)
    table.add_column("Slot Decay Per Second", style="blue", no_wrap=True)

    for gcl_limit in sorted(gcl_limits, key=lambda x: f"{x.name}"):
        table.add_row(
            str(gcl_limit.id),
            pendulum.instance(gcl_limit.created).isoformat(),
            pendulum.instance(gcl_limit.updated).diff_for_humans(),
            str(gcl_limit.active),
            gcl_limit.name,
            str(gcl_limit.limit),
            str(gcl_limit.active_slots),
            str(gcl_limit.slot_decay_per_second),
        )

    app.console.print(table)


@global_concurrency_limit_app.command("inspect")
async def inspect_global_concurrency_limit(
    name: str,
    output: Optional[OutputFormat] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output format for the command.",
        # choices are json
        # not case sensitive
        case_sensitive=False,
    ),
    file_path: Optional[Path] = typer.Option(
        None,
        "--file",
        "-f",
        help="Path to .py file containing block types to be registered",
    ),
):
    """
    Inspect a global concurrency limit.

    Arguments:
        name: str: [required]
            - The name of the global concurrency limit to inspect.
        output: Optional[OutputFormat]: [optional]
            - Output format for the command.
        file_path: Optional[Path]: [optional]
            - Path to .py file containing block types to be registered

    Returns:
        - str: The name of the global concurrency limit.
        - int: The limit of the global concurrency limit.
        - int: The number of active slots.
        - float: The slot decay per second.

    """
    if file_path and not output:
        exit_with_error("The --file/-f option requires the --output option to be set.")

    async with get_client() as client:
        try:
            gcl_limit = await client.read_global_concurrency_limit_by_name(name=name)
        except ObjectNotFound:
            exit_with_error(f"Global Concurrency Limit {name!r} not found.")

    if output is not None and output.value == "json":
        gcl_limit = gcl_limit.dict(json_compatible=True)
        json_output = orjson.dumps(gcl_limit, option=orjson.OPT_INDENT_2).decode()
        if not file_path:
            app.console.print(json_output)

        else:
            with open(file_path, "w") as f:
                f.write(json_output)

    else:
        app.console.print(Pretty(gcl_limit))
