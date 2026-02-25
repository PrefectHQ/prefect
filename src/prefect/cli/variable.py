"""
Variable command — native cyclopts implementation.

Manage Prefect variables.
"""

import json
from typing import Annotated, Any, Optional, Union

import cyclopts

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

variable_app: cyclopts.App = cyclopts.App(
    name="variable",
    help="Manage variables.",
    version_flags=[],
    help_flags=["--help"],
)


def _parse_value(
    value: str,
) -> Union[str, int, float, bool, None, dict[str, Any], list[str]]:
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        parsed_value = value
    return parsed_value


@variable_app.command(name="ls")
@with_cli_exception_handling
async def list_variables(
    *,
    limit: Annotated[
        int,
        cyclopts.Parameter(
            "--limit", help="The maximum number of variables to return."
        ),
    ] = 100,
    output: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--output",
            alias="-o",
            help="Specify an output format. Currently supports: json",
        ),
    ] = None,
):
    """List variables."""
    import orjson
    from rich.table import Table

    from prefect.client.orchestration import get_client
    from prefect.types._datetime import human_friendly_diff

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    async with get_client() as client:
        variables = await client.read_variables(limit=limit)

    if output and output.lower() == "json":
        variables_json = [variable.model_dump(mode="json") for variable in variables]
        json_output = orjson.dumps(variables_json, option=orjson.OPT_INDENT_2).decode()
        _cli.console.print(json_output)
    else:
        table = Table(
            title="Variables",
            caption="List Variables using `prefect variable ls`",
            show_header=True,
        )

        table.add_column("Name", style="blue", no_wrap=True)
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

        _cli.console.print(table)


@variable_app.command(name="inspect")
@with_cli_exception_handling
async def inspect(
    name: str,
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
    """View details about a variable."""
    import orjson
    from rich.pretty import Pretty

    from prefect.client.orchestration import get_client

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    async with get_client() as client:
        variable = await client.read_variable_by_name(name=name)
        if not variable:
            exit_with_error(f"Variable {name!r} not found.")

        if output and output.lower() == "json":
            variable_json = variable.model_dump(mode="json")
            json_output = orjson.dumps(
                variable_json, option=orjson.OPT_INDENT_2
            ).decode()
            _cli.console.print(json_output)
        else:
            _cli.console.print(Pretty(variable))


@variable_app.command(name="get")
@with_cli_exception_handling
async def get(name: str):
    """Get a variable's value."""
    from prefect.client.orchestration import get_client

    async with get_client() as client:
        variable = await client.read_variable_by_name(name=name)
        if variable:
            _cli.console.print(json.dumps(variable.value))
        else:
            exit_with_error(f"Variable {name!r} not found.")


@variable_app.command(name="set")
@with_cli_exception_handling
async def _set(
    name: str,
    value: str,
    *,
    overwrite: Annotated[
        bool,
        cyclopts.Parameter(
            "--overwrite", help="Overwrite the variable if it already exists."
        ),
    ] = False,
    tag: Annotated[
        Optional[list[str]],
        cyclopts.Parameter("--tag", help="Tag to associate with the variable."),
    ] = None,
):
    """Set a variable.

    If the variable already exists, use `--overwrite` to update it.
    """
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import VariableCreate, VariableUpdate

    async with get_client() as client:
        variable = await client.read_variable_by_name(name)
        var_dict = {"name": name, "value": _parse_value(value), "tags": tag or []}
        if variable:
            if not overwrite:
                exit_with_error(
                    f"Variable {name!r} already exists. Use `--overwrite` to update it."
                )
            await client.update_variable(VariableUpdate(**var_dict))
        else:
            await client.create_variable(VariableCreate(**var_dict))

        exit_with_success(f"Set variable {name!r}.")


@variable_app.command(name="unset")
@with_cli_exception_handling
async def unset(name: str):
    """Unset a variable."""
    from prefect.cli._prompts import confirm
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    async with get_client() as client:
        try:
            if _cli.is_interactive() and not confirm(
                f"Are you sure you want to unset variable {name!r}?",
                console=_cli.console,
            ):
                exit_with_error("Unset aborted.")
            await client.delete_variable_by_name(name=name)
        except ObjectNotFound:
            exit_with_error(f"Variable {name!r} not found.")

        exit_with_success(f"Unset variable {name!r}.")


# Alias: ``prefect variable delete`` → ``prefect variable unset``
variable_app.command(unset, name="delete")
