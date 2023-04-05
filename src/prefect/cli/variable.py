import pendulum
import typer
from rich.pretty import Pretty
from rich.table import Table

from prefect import get_client
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.exceptions import ObjectNotFound

variable_app = PrefectTyper(
    name="variable", help="Commands for interacting with variables."
)
app.add_typer(variable_app)


@variable_app.command("ls")
async def list_variables(
    limit: int = typer.Option(
        100,
        "--limit",
        help="The maximum number of variables to return.",
    ),
):
    """
    List variables.
    """
    async with get_client() as client:
        variables = await client.read_variables(
            limit=limit,
        )

        table = Table(
            title="Variables",
            caption="List Variables using `prefect variable ls`",
            show_header=True,
        )

        table.add_column("Name", style="blue", no_wrap=True)
        # values can be up 5000 characters so truncate early
        table.add_column("Value", style="blue", no_wrap=True, max_width=50)
        table.add_column("Created", style="blue", no_wrap=True)
        table.add_column("Updated", style="blue", no_wrap=True)

        for variable in sorted(variables, key=lambda x: f"{x.name}"):
            table.add_row(
                variable.name,
                variable.value,
                pendulum.instance(variable.created).diff_for_humans(),
                pendulum.instance(variable.updated).diff_for_humans(),
            )

        app.console.print(table)


@variable_app.command("inspect")
async def inspect(
    name: str,
):
    """
    View details about a variable.

    Arguments:
        name: the name of the variable to inspect
    """

    async with get_client() as client:
        variable = await client.read_variable_by_name(
            name=name,
        )
        if not variable:
            exit_with_error(f"Variable {name!r} not found.")

        app.console.print(Pretty(variable))


@variable_app.command("delete")
async def delete(
    name: str,
):
    """
    Delete a variable.

    Arguments:
        name: the name of the variable to delete
    """

    async with get_client() as client:
        try:
            await client.delete_variable_by_name(
                name=name,
            )
        except ObjectNotFound:
            exit_with_error(f"Variable {name!r} not found.")

        exit_with_success(f"Deleted variable {name!r}.")
