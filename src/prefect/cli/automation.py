"""
Automation command — native cyclopts implementation.

Manage automations.
"""

import asyncio
from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID

import cyclopts

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

automation_app: cyclopts.App = cyclopts.App(
    name="automation",
    alias="automations",
    help="Manage automations.",
    version_flags=[],
    help_flags=["--help"],
)


@automation_app.command(name="ls")
@with_cli_exception_handling
async def ls():
    """List all automations."""
    from rich.table import Table
    from rich.text import Text

    from prefect.client.orchestration import get_client

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

    _cli.console.print(table)


@automation_app.command(name="inspect")
@with_cli_exception_handling
async def inspect(
    name: Annotated[Optional[str], cyclopts.Parameter(show=False)] = None,
    *,
    id: Annotated[
        Optional[str],
        cyclopts.Parameter("--id", help="An automation's id"),
    ] = None,
    yaml: Annotated[
        bool,
        cyclopts.Parameter("--yaml", help="Output as YAML"),
    ] = False,
    json: Annotated[
        bool,
        cyclopts.Parameter("--json", help="Output as JSON"),
    ] = False,
    output: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--output",
            alias="-o",
            help="Specify an output format. Currently supports: json, yaml",
        ),
    ] = None,
):
    """Inspect an automation."""
    import orjson
    import yaml as pyyaml
    from pydantic import BaseModel
    from rich.pretty import Pretty

    from prefect.client.orchestration import get_client
    from prefect.events.schemas.automations import Automation
    from prefect.exceptions import PrefectHTTPStatusError

    if output and output.lower() not in ["json", "yaml"]:
        exit_with_error("Only 'json' and 'yaml' output formats are supported.")

    if not id and not name:
        exit_with_error("Please provide either a name or an id.")

    automation: Automation | list[Automation] | None = None

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

    if yaml or json or (output and output.lower() in ["json", "yaml"]):

        def no_really_json(obj: type[BaseModel]):
            return orjson.loads(obj.model_dump_json())

        if isinstance(automation, list):
            automation = [no_really_json(a) for a in automation]
        elif isinstance(automation, Automation):
            automation = no_really_json(automation)

        if yaml or (output and output.lower() == "yaml"):
            _cli.console.print(pyyaml.dump(automation, sort_keys=False))
        elif json or (output and output.lower() == "json"):
            _cli.console.print(
                orjson.dumps(automation, option=orjson.OPT_INDENT_2).decode()
            )
    else:
        _cli.console.print(Pretty(automation))


@automation_app.command(name="resume", alias="enable")
@with_cli_exception_handling
async def resume(
    name: Annotated[Optional[str], cyclopts.Parameter(show=False)] = None,
    *,
    id: Annotated[
        Optional[str],
        cyclopts.Parameter("--id", help="An automation's id"),
    ] = None,
):
    """Resume an automation."""
    from prefect.client.orchestration import get_client
    from prefect.exceptions import PrefectHTTPStatusError

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
                from prefect.cli._prompts import confirm

                if not confirm(
                    f"Multiple automations found with name {name!r}. Do you want to resume all of them?",
                    default=False,
                    console=_cli.console,
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


@automation_app.command(name="pause", alias="disable")
@with_cli_exception_handling
async def pause(
    name: Annotated[Optional[str], cyclopts.Parameter(show=False)] = None,
    *,
    id: Annotated[
        Optional[str],
        cyclopts.Parameter("--id", help="An automation's id"),
    ] = None,
):
    """Pause an automation."""
    from prefect.client.orchestration import get_client
    from prefect.exceptions import PrefectHTTPStatusError

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
                from prefect.cli._prompts import confirm

                if not confirm(
                    f"Multiple automations found with name {name!r}. Do you want to pause all of them?",
                    default=False,
                    console=_cli.console,
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


@automation_app.command(name="delete")
@with_cli_exception_handling
async def delete(
    name: Annotated[Optional[str], cyclopts.Parameter(show=False)] = None,
    *,
    id: Annotated[
        Optional[str],
        cyclopts.Parameter("--id", help="An automation's id"),
    ] = None,
    all: Annotated[
        bool,
        cyclopts.Parameter("--all", help="Delete all automations"),
    ] = False,
):
    """Delete an automation."""
    from prefect.client.orchestration import get_client

    async with get_client() as client:
        if all:
            if name is not None or id is not None:
                exit_with_error(
                    "Cannot provide an automation name or id when deleting all automations."
                )
            automations = await client.read_automations()
            if len(automations) == 0:
                exit_with_success("No automations found.")

            if _cli.is_interactive():
                from prefect.cli._prompts import confirm

                if not confirm(
                    f"Are you sure you want to delete all {len(automations)} automations?",
                    default=False,
                    console=_cli.console,
                ):
                    exit_with_error("Deletion aborted.")

            semaphore = asyncio.Semaphore(10)

            async def limited_delete(automation_id):
                async with semaphore:
                    await client.delete_automation(automation_id)

            await asyncio.gather(
                *[limited_delete(automation.id) for automation in automations]
            )

            plural = "" if len(automations) == 1 else "s"
            exit_with_success(f"Deleted {len(automations)} automation{plural}.")

        if not id and not name:
            exit_with_error("Please provide either a name or an id.")

        if id:
            automation = await client.read_automation(id)
            if not automation:
                exit_with_error(f"Automation with id {id!r} not found.")

            if _cli.is_interactive():
                from prefect.cli._prompts import confirm

                if not confirm(
                    f"Are you sure you want to delete automation with id {id!r}?",
                    default=False,
                    console=_cli.console,
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

            if _cli.is_interactive():
                from prefect.cli._prompts import confirm

                if not confirm(
                    f"Are you sure you want to delete automation with name {name!r}?",
                    default=False,
                    console=_cli.console,
                ):
                    exit_with_error("Deletion aborted.")
            await client.delete_automation(automation[0].id)
            exit_with_success(f"Deleted automation with name {name!r}")


@automation_app.command(name="create")
@with_cli_exception_handling
async def create(
    *,
    from_file: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--from-file",
            alias="-f",
            help="Path to YAML or JSON file containing automation(s)",
        ),
    ] = None,
    from_json: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--from-json",
            alias="-j",
            help="JSON string containing automation(s)",
        ),
    ] = None,
):
    """Create one or more automations from a file or JSON string."""
    import orjson
    import yaml as pyyaml

    from prefect.client.orchestration import get_client
    from prefect.events.schemas.automations import AutomationCore

    if from_file and from_json:
        exit_with_error("Please provide either --from-file or --from-json, not both.")

    if not from_file and not from_json:
        exit_with_error("Please provide either --from-file or --from-json.")

    if from_file:
        file_path = Path(from_file)
        if not file_path.exists():
            exit_with_error(f"File not found: {from_file}")

        with open(file_path, "r") as f:
            content = f.read()

        if file_path.suffix.lower() in [".yaml", ".yml"]:
            data = pyyaml.safe_load(content)
        elif file_path.suffix.lower() == ".json":
            data = orjson.loads(content)
        else:
            exit_with_error(
                "File extension not recognized. Please use .yaml, .yml, or .json"
            )
    else:  # from_json
        try:
            data = orjson.loads(from_json)
        except orjson.JSONDecodeError as e:
            exit_with_error(f"Invalid JSON: {e}")

    automations_data = []
    if isinstance(data, dict) and "automations" in data:
        automations_data = data["automations"]
    elif isinstance(data, list):
        automations_data = data
    else:
        automations_data = [data]

    created = []
    failed = []
    async with get_client() as client:
        for i, automation_data in enumerate(automations_data):
            try:
                automation = AutomationCore.model_validate(automation_data)
                automation_id = await client.create_automation(automation)
                created.append((automation.name, automation_id))
            except Exception as e:
                name = automation_data.get("name", f"automation at index {i}")
                failed.append((name, str(e)))

    if failed:
        _cli.console.print(f"[red]Failed to create {len(failed)} automation(s):[/red]")
        for name, error in failed:
            _cli.console.print(f"  - {name}: {error}")

    if created:
        if len(created) == 1 and not failed:
            name, automation_id = created[0]
            exit_with_success(f"Created automation '{name}' with id {automation_id}")
        else:
            _cli.console.print(f"[green]Created {len(created)} automation(s):[/green]")
            for name, automation_id in created:
                _cli.console.print(f"  - '{name}' with id {automation_id}")

    if failed:
        raise SystemExit(1)
    else:
        raise SystemExit(0)


@automation_app.command(name="update")
@with_cli_exception_handling
async def update(
    *,
    id: Annotated[
        str,
        cyclopts.Parameter("--id", help="The ID of the automation to update"),
    ],
    from_file: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--from-file",
            alias="-f",
            help="Path to YAML or JSON file containing the updated automation",
        ),
    ] = None,
    from_json: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--from-json",
            alias="-j",
            help="JSON string containing the updated automation",
        ),
    ] = None,
):
    """Update an existing automation from a file or JSON string."""
    import orjson
    import yaml as pyyaml

    from prefect.client.orchestration import get_client
    from prefect.events.schemas.automations import AutomationCore
    from prefect.exceptions import PrefectHTTPStatusError

    if from_file and from_json:
        exit_with_error("Please provide either --from-file or --from-json, not both.")

    if not from_file and not from_json:
        exit_with_error("Please provide either --from-file or --from-json.")

    try:
        automation_id = UUID(id)
    except ValueError:
        exit_with_error(f"Invalid automation ID: {id!r}")

    if from_file:
        file_path = Path(from_file)
        if not file_path.exists():
            exit_with_error(f"File not found: {from_file}")

        with open(file_path, "r") as f:
            content = f.read()

        if file_path.suffix.lower() in [".yaml", ".yml"]:
            data = pyyaml.safe_load(content)
        elif file_path.suffix.lower() == ".json":
            data = orjson.loads(content)
        else:
            exit_with_error(
                "File extension not recognized. Please use .yaml, .yml, or .json"
            )
    else:  # from_json
        try:
            data = orjson.loads(from_json)
        except orjson.JSONDecodeError as e:
            exit_with_error(f"Invalid JSON: {e}")

    try:
        automation = AutomationCore.model_validate(data)
    except Exception as e:
        exit_with_error(f"Automation config failed validation: {e}")

    async with get_client() as client:
        try:
            existing_automation = await client.read_automation(automation_id)
        except PrefectHTTPStatusError as e:
            if e.response.status_code == 404:
                exit_with_error(f"Automation with id {id!r} not found.")
            raise

        if not existing_automation:
            exit_with_error(f"Automation with id {id!r} not found.")

        await client.update_automation(automation_id, automation)
        exit_with_success(f"Updated automation '{automation.name}' ({id})")
