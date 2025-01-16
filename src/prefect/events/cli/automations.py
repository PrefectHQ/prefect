"""
Command line interface for working with automations.
"""

import functools
from typing import Any, Callable, Optional, Type
from uuid import UUID

import orjson
import typer
import yaml as pyyaml
from pydantic import BaseModel
from rich.pretty import Pretty
from rich.table import Table
from rich.text import Text

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app, is_interactive
from prefect.client.orchestration import get_client
from prefect.events.schemas.automations import Automation
from prefect.exceptions import PrefectHTTPStatusError

automations_app: PrefectTyper = PrefectTyper(
    name="automation",
    help="Manage automations.",
)
app.add_typer(automations_app, aliases=["automations"])


def requires_automations(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
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
async def inspect(
    name: Optional[str] = typer.Argument(None, help="An automation's name"),
    id: Optional[str] = typer.Option(None, "--id", help="An automation's id"),
    yaml: bool = typer.Option(False, "--yaml", help="Output as YAML"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Inspect an automation.

    Arguments:

        name: the name of the automation to inspect

        id: the id of the automation to inspect

        yaml: output as YAML

        json: output as JSON

    Examples:

        $ prefect automation inspect "my-automation"

        $ prefect automation inspect --id "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        $ prefect automation inspect "my-automation" --yaml

        $ prefect automation inspect "my-automation" --json
    """
    if not id and not name:
        exit_with_error("Please provide either a name or an id.")

    if name:
        async with get_client() as client:
            automation = await client.read_automations_by_name(name=name)
            if not automation:
                exit_with_error(f"Automation {name!r} not found.")

    elif id:
        async with get_client() as client:
            try:
                uuid_id = UUID(id)
                automation = await client.read_automation(uuid_id)
            except (PrefectHTTPStatusError, ValueError):
                exit_with_error(f"Automation with id {id!r} not found.")

    if yaml or json:

        def no_really_json(obj: Type[BaseModel]):
            # Working around a weird bug where pydantic isn't rendering enums as strings
            #
            # automation.trigger.model_dump(mode="json")
            # {..., 'posture': 'Reactive', ...}
            #
            # automation.model_dump(mode="json")
            # {..., 'posture': Posture.Reactive, ...}
            return orjson.loads(obj.model_dump_json())

        if isinstance(automation, list):
            automation = [no_really_json(a) for a in automation]
        elif isinstance(automation, Automation):
            automation = no_really_json(automation)

        if yaml:
            app.console.print(pyyaml.dump(automation, sort_keys=False))
        elif json:
            app.console.print(
                orjson.dumps(automation, option=orjson.OPT_INDENT_2).decode()
            )
    else:
        app.console.print(Pretty(automation))


@automations_app.command(aliases=["enable"])
@requires_automations
async def resume(
    name: Optional[str] = typer.Argument(None, help="An automation's name"),
    id: Optional[str] = typer.Option(None, "--id", help="An automation's id"),
):
    """
    Resume an automation.

    Arguments:

            name: the name of the automation to resume

            id: the id of the automation to resume

    Examples:

            $ prefect automation resume "my-automation"

            $ prefect automation resume --id "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    """
    if not id and not name:
        exit_with_error("Please provide either a name or an id.")

    if name:
        async with get_client() as client:
            automation = await client.read_automations_by_name(name=name)
            if not automation:
                exit_with_error(
                    f"Automation with name {name!r} not found. You can also specify an id with the `--id` flag."
                )
            if len(automation) > 1:
                if not typer.confirm(
                    f"Multiple automations found with name {name!r}. Do you want to resume all of them?",
                    default=False,
                ):
                    exit_with_error("Resume aborted.")

            for a in automation:
                await client.resume_automation(a.id)
            exit_with_success(
                f"Resumed automation(s) with name {name!r} and id(s) {', '.join([repr(str(a.id)) for a in automation])}."
            )

    elif id:
        async with get_client() as client:
            try:
                uuid_id = UUID(id)
                automation = await client.read_automation(uuid_id)
            except (PrefectHTTPStatusError, ValueError):
                exit_with_error(f"Automation with id {id!r} not found.")
            await client.resume_automation(automation.id)
            exit_with_success(f"Resumed automation with id {str(automation.id)!r}.")


@automations_app.command(aliases=["disable"])
@requires_automations
async def pause(
    name: Optional[str] = typer.Argument(None, help="An automation's name"),
    id: Optional[str] = typer.Option(None, "--id", help="An automation's id"),
):
    """
    Pause an automation.

    Arguments:

            name: the name of the automation to pause

            id: the id of the automation to pause

    Examples:

        $ prefect automation pause "my-automation"

        $ prefect automation pause --id "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    """
    if not id and not name:
        exit_with_error("Please provide either a name or an id.")

    if name:
        async with get_client() as client:
            automation = await client.read_automations_by_name(name=name)
            if not automation:
                exit_with_error(
                    f"Automation with name {name!r} not found. You can also specify an id with the `--id` flag."
                )
            if len(automation) > 1:
                if not typer.confirm(
                    f"Multiple automations found with name {name!r}. Do you want to pause all of them?",
                    default=False,
                ):
                    exit_with_error("Pause aborted.")

            for a in automation:
                await client.pause_automation(a.id)
            exit_with_success(
                f"Paused automation(s) with name {name!r} and id(s) {', '.join([repr(str(a.id)) for a in automation])}."
            )

    elif id:
        async with get_client() as client:
            try:
                uuid_id = UUID(id)
                automation = await client.read_automation(uuid_id)
            except (PrefectHTTPStatusError, ValueError):
                exit_with_error(f"Automation with id {id!r} not found.")
            await client.pause_automation(automation.id)
            exit_with_success(f"Paused automation with id {str(automation.id)!r}.")


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
            if is_interactive() and not typer.confirm(
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
            if is_interactive() and not typer.confirm(
                (f"Are you sure you want to delete automation with name {name!r}?"),
                default=False,
            ):
                exit_with_error("Deletion aborted.")
            await client.delete_automation(automation[0].id)
            exit_with_success(f"Deleted automation with name {name!r}")
