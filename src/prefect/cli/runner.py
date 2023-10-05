import typer
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from typing_extensions import Annotated

from prefect._internal.concurrency.api import create_call, from_async
from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.runner.runner import Runner
from prefect.settings import PREFECT_UI_URL
from prefect.utilities.importtools import import_object

runner_cli_app = PrefectTyper(
    name="runner",
    help="Commands for working with runners.",
)

app.add_typer(runner_cli_app)


@runner_cli_app.command()
async def serve(
    entrypoint: Annotated[
        str,
        typer.Argument(
            ...,
            help=(
                "The entrypoint for the runner. Should be in the format"
                " path/to/runner_file.py:runner_variable_name"
            ),
        ),
    ],
):
    """
    Starts up the specified runner to serve the registered flows.
    """
    runner: Runner = await from_async.wait_for_call_in_new_thread(
        create_call(import_object, entrypoint)
    )

    help_message_top = (
        "[green]Your deployments are being served and your runner is polling for"
        " scheduled runs!\n[/]"
    )

    table = Table(title="Deployments", show_header=False)

    table.add_column(style="blue", no_wrap=True)

    for deployment in runner.registered_deployments:
        table.add_row(f"{deployment.flow_name}/{deployment.name}")

    help_message_bottom = (
        "\nTo trigger any of these deployments, use the"
        " following command:\n[blue]\n\t$ prefect deployment run"
        " [DEPLOYMENT_NAME]\n[/]"
    )
    if PREFECT_UI_URL:
        help_message_bottom += (
            "\nYou can also trigger your deployments via the Prefect UI:"
            f" [blue]{PREFECT_UI_URL.value()}/deployments[/]\n"
        )

    app.console.print(Panel(Group(help_message_top, table, help_message_bottom)))

    await runner.start()
