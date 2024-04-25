"""
Command line interface for working with automations.
"""

import functools
from typing import Optional

import orjson
import typer
import yaml as pyyaml
from rich.pretty import Pretty
from rich.table import Table
from rich.text import Text

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client.orchestration import get_client

automations_app = PrefectTyper(
    name="automation",
    help="Commands for managing automations.",
)
app.add_typer(automations_app, aliases=["automations"])


def requires_automations(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except RuntimeError as exc:
            if "Enable experimental" in str(exc):
                exit_with_error(str(exc))
            raise

    return wrapper


@automations_app.command()
@requires_automations
async def ls():
    """List all automations."""
    async with get_client() as client:
        automations = await client.read_automations()

    table = Table(title="Automations", show_lines=True)

    table.add_column("Automation")
    table.add_column("Enabled")
    table.add_column("Trigger")
    table.add_column("Actions")

    for automation in automations:
        identifier_column = Text()

        identifier_column.append(automation.name, style="white bold")
        identifier_column.append("\n")

        identifier_column.append(str(automation.id), style="cyan")
        identifier_column.append("\n")

        if automation.description:
            identifier_column.append(automation.description, style="white")
            identifier_column.append("\n")

        if automation.actions_on_trigger or automation.actions_on_resolve:
            actions = (
                [
                    f"(trigger) {action.describe_for_cli()}"
                    for action in automation.actions
                ]
                + [
                    f"(trigger) {action.describe_for_cli()}"
                    for action in automation.actions_on_trigger
                ]
                + [
                    f"(resolve) {action.describe_for_cli()}"
                    for action in automation.actions
                ]
                + [
                    f"(resolve) {action.describe_for_cli()}"
                    for action in automation.actions_on_resolve
                ]
            )
        else:
            actions = [action.describe_for_cli() for action in automation.actions]

        table.add_row(
            identifier_column,
            str(automation.enabled),
            automation.trigger.describe_for_cli(),
            "\n".join(actions),
        )

    app.console.print(table)


@automations_app.command()
@requires_automations
async def inspect(id_or_name: str, yaml: bool = False, json: bool = False):
    """Inspect an automation."""
    async with get_client() as client:
        automation = await client.find_automation(id_or_name)
        if not automation:
            exit_with_error(f"Automation {id_or_name!r} not found.")

    if yaml:
        app.console.print(
            pyyaml.dump(automation.dict(json_compatible=True), sort_keys=False)
        )
    elif json:
        app.console.print(
            orjson.dumps(
                automation.dict(json_compatible=True), option=orjson.OPT_INDENT_2
            ).decode()
        )
    else:
        app.console.print(Pretty(automation))


@automations_app.command(aliases=["enable"])
@requires_automations
async def resume(id_or_name: str):
    """Resume an automation."""
    async with get_client() as client:
        automation = await client.find_automation(id_or_name)
        if not automation:
            exit_with_error(f"Automation {id_or_name!r} not found.")

    async with get_client() as client:
        await client.resume_automation(automation.id)

    exit_with_success(f"Resumed automation {automation.name!r} ({automation.id})")


@automations_app.command(aliases=["disable"])
@requires_automations
async def pause(id_or_name: str):
    """Pause an automation."""
    async with get_client() as client:
        automation = await client.find_automation(id_or_name)
        if not automation:
            exit_with_error(f"Automation {id_or_name!r} not found.")

    async with get_client() as client:
        await client.pause_automation(automation.id)

    exit_with_success(f"Paused automation {automation.name!r} ({automation.id})")


@automations_app.command()
@requires_automations
async def delete(
    name: Optional[str] = typer.Argument(None, help="An automation's name"),
    id: Optional[str] = typer.Option(None, "--id", help="An automation's id"),
):
    """Delete an automation.

    Arguments:
        name: the name of the automation to delete
        id: the id of the automation to delete

    Examples:
        $ prefect automation delete "my-automation"
        $ prefect automation delete --id "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    """

    async with get_client() as client:
        if not id and not name:
            exit_with_error("Please provide either a name or an id.")

        if id:
            automation = await client.read_automation(id)
            if not automation:
                exit_with_error(f"Automation with id {id!r} not found.")
            if not typer.confirm(
                (f"Are you sure you want to delete automation with id {id!r}?"),
                default=False,
            ):
                exit_with_error("Deletion aborted.")
            await client.delete_automation(id)
            exit_with_success(f"Deleted automation with id {id!r}")

        elif name:
            automation = await client.read_automations_by_name(name=name)
            if not automation:
                exit_with_error(
                    f"Automation {name!r} not found. You can also specify an id with the `--id` flag."
                )
            elif len(automation) > 1:
                exit_with_error(
                    f"Multiple automations found with name {name!r}. Please specify an id with the `--id` flag instead."
                )
            if not typer.confirm(
                (f"Are you sure you want to delete automation with name {name!r}?"),
                default=False,
            ):
                exit_with_error("Deletion aborted.")
            await client.delete_automation(automation[0].id)
            exit_with_success(f"Deleted automation with name {name!r}")
