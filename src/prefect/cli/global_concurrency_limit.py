import pendulum
from rich.table import Table

from prefect import get_client
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_success
from prefect.cli.root import app

global_concurrency_limit_app = PrefectTyper(
    name="global-concurrency-limit",
    help="Commands for managing global concurrency limits.",
)

app.add_typer(global_concurrency_limit_app, aliases=["gcl"])


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
    table.add_column("Name", style="blue", no_wrap=True, overflow="fold", width=40)
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
