import json
from typing import Any, Dict, List, Optional, Union

import orjson
import typer
from rich.pretty import Pretty
from rich.table import Table
from typing_extensions import Annotated

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app, is_interactive
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import VariableCreate, VariableUpdate
from prefect.exceptions import ObjectNotFound
from prefect.types._datetime import human_friendly_diff

variable_app: PrefectTyper = PrefectTyper(name="variable", help="Manage variables.")
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
            assert variable.created is not None, "created is not None"
            assert variable.updated is not None, "updated is not None"
            table.add_row(
                variable.name,
                json.dumps(variable.value),
                human_friendly_diff(variable.created),
                human_friendly_diff(variable.updated),
            )

        app.console.print(table)


@variable_app.command("inspect")
async def inspect(
    name: str,
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Specify an output format. Currently supports: json",
    ),
):
    """
    View details about a variable.

    Arguments:
        name: the name of the variable to inspect
    """
    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    async with get_client() as client:
        variable = await client.read_variable_by_name(
            name=name,
        )
        if not variable:
            exit_with_error(f"Variable {name!r} not found.")

        if output and output.lower() == "json":
            variable_json = variable.model_dump(mode="json")
            json_output = orjson.dumps(
                variable_json, option=orjson.OPT_INDENT_2
            ).decode()
            app.console.print(json_output)
        else:
            app.console.print(Pretty(variable))


@variable_app.command("get")
async def get(
    name: str,
):
    """
    Get a variable's value.

    Arguments:
        name: the name of the variable to get
    """

    async with get_client() as client:
        variable = await client.read_variable_by_name(
            name=name,
        )
        if variable:
            app.console.print(json.dumps(variable.value))
        else:
            exit_with_error(f"Variable {name!r} not found.")


def parse_value(
    value: str,
) -> Union[str, int, float, bool, None, Dict[str, Any], List[str]]:
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        parsed_value = value
    return parsed_value


@variable_app.command("set")
async def _set(
    name: str,
    value: str,
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite the variable if it already exists.",
    ),
    tag: Annotated[
        Optional[List[str]], typer.Option(help="Tag to associate with the variable.")
    ] = None,
):
    """
    Set a variable.

    If the variable already exists, use `--overwrite` to update it.

    Arguments:
        name: the name of the variable to set
        value: the value of the variable to set
        --overwrite: overwrite the variable if it already exists
        --tag: tag to associate with the variable (you may pass multiple)
    """

    async with get_client() as client:
        variable = await client.read_variable_by_name(name)
        var_dict = {"name": name, "value": parse_value(value), "tags": tag or []}
        if variable:
            if not overwrite:
                exit_with_error(
                    f"Variable {name!r} already exists. Use `--overwrite` to update it."
                )
            await client.update_variable(VariableUpdate(**var_dict))
        else:
            await client.create_variable(VariableCreate(**var_dict))

        exit_with_success(f"Set variable {name!r}.")


@variable_app.command("unset", aliases=["delete"])
async def unset(
    name: str,
):
    """
    Unset a variable.

    Arguments:
        name: the name of the variable to unset
    """

    async with get_client() as client:
        try:
            if is_interactive() and not typer.confirm(
                f"Are you sure you want to unset variable {name!r}?"
            ):
                exit_with_error("Unset aborted.")
            await client.delete_variable_by_name(
                name=name,
            )
        except ObjectNotFound:
            exit_with_error(f"Variable {name!r} not found.")

        exit_with_success(f"Unset variable {name!r}.")
