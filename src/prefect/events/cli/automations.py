"""
Command line interface for working with automations.
"""

import orjson
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


@automations_app.command()
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
async def delete(id_or_name: str):
    """Delete an automation."""
    async with get_client() as client:
        automation = await client.find_automation(id_or_name)

    if not automation:
        exit_with_success(f"Automation {id_or_name!r} not found")

    async with get_client() as client:
        await client.delete_automation(automation.id)

    exit_with_success(f"Deleted automation {automation.name!r} ({automation.id})")
