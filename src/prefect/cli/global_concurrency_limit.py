from pathlib import Path
from typing import Optional

import orjson
import typer
from pydantic import ValidationError
from rich.pretty import Pretty
from rich.table import Table

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app, is_interactive
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import (
    GlobalConcurrencyLimitCreate,
    GlobalConcurrencyLimitUpdate,
)
from prefect.exceptions import (
    ObjectNotFound,
    PrefectHTTPStatusError,
)
from prefect.types._datetime import human_friendly_diff

global_concurrency_limit_app: PrefectTyper = PrefectTyper(
    name="global-concurrency-limit",
    help="Manage global concurrency limits.",
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
    table.add_column("Name", style="blue", no_wrap=True, overflow="fold")
    table.add_column("Active", style="blue", no_wrap=True)
    table.add_column("Limit", style="blue", no_wrap=True)
    table.add_column("Active Slots", style="blue", no_wrap=True)
    table.add_column("Slot Decay Per Second", style="blue", no_wrap=True)
    table.add_column("Created", style="blue", no_wrap=True)
    table.add_column("Updated", style="blue", no_wrap=True)

    for gcl_limit in sorted(gcl_limits, key=lambda x: f"{x.name}"):
        assert gcl_limit.created is not None, "created is not None"
        assert gcl_limit.updated is not None, "updated is not None"
        table.add_row(
            str(gcl_limit.id),
            gcl_limit.name,
            str(gcl_limit.active),
            str(gcl_limit.limit),
            str(gcl_limit.active_slots),
            str(gcl_limit.slot_decay_per_second),
            gcl_limit.created.isoformat(),
            human_friendly_diff(gcl_limit.updated),
        )

    app.console.print(table)


@global_concurrency_limit_app.command("inspect")
async def inspect_global_concurrency_limit(
    name: str = typer.Argument(
        ..., help="The name of the global concurrency limit to inspect."
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Specify an output format. Currently supports: json",
    ),
    file_path: Optional[Path] = typer.Option(
        None,
        "--file",
        "-f",
        help="Path to .json file to write the global concurrency limit output to.",
    ),
):
    """
    Inspect a global concurrency limit.

    Arguments:
        name (str): The name of the global concurrency limit to inspect.
        output (Optional[OutputFormat]): An output format for the command. Currently only supports JSON.
            Required if --file/-f is set.
        file_path (Optional[Path]): A path to .json file to write the global concurrent limit output to.

    Returns:
        id (str): The ID of the global concurrency limit.
        created (str): The created date of the global concurrency limit.
        updated (str): The updated date of the global concurrency limit.
        name (str): The name of the global concurrency limit.
        limit (int): The limit of the global concurrency limit.
        active_slots (int): The number of active slots.
        slot_decay_per_second (float): The slot decay per second.

    """
    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    if file_path and not output:
        exit_with_error("The --file/-f option requires the --output option to be set.")

    async with get_client() as client:
        try:
            gcl_limit = await client.read_global_concurrency_limit_by_name(name=name)
        except ObjectNotFound:
            exit_with_error(f"Global concurrency limit {name!r} not found.")

    if output and output.lower() == "json":
        gcl_limit_json = gcl_limit.model_dump(mode="json")
        json_output = orjson.dumps(gcl_limit_json, option=orjson.OPT_INDENT_2).decode()
        if not file_path:
            app.console.print(json_output)
        else:
            with open(file_path, "w") as f:
                f.write(json_output)
                exit_with_success(
                    f"Global concurrency limit {name!r} written to {file_path}"
                )
    else:
        app.console.print(Pretty(gcl_limit))


@global_concurrency_limit_app.command("delete")
async def delete_global_concurrency_limit(
    name: str = typer.Argument(
        ..., help="The name of the global concurrency limit to delete."
    ),
):
    """
    Delete a global concurrency limit.

    Arguments:
        name (str): The name of the global concurrency limit to delete.
    """
    async with get_client() as client:
        try:
            gcl_limit = await client.read_global_concurrency_limit_by_name(name=name)

            if is_interactive() and not typer.confirm(
                f"Are you sure you want to delete global concurrency limit with name {gcl_limit.name!r}?",
                default=False,
            ):
                exit_with_error("Deletion aborted.")

            await client.delete_global_concurrency_limit_by_name(name=name)
        except ObjectNotFound:
            exit_with_error(f"Global concurrency limit {name!r} not found.")

    exit_with_success(f"Deleted global concurrency limit with name {name!r}.")


@global_concurrency_limit_app.command("enable")
async def enable_global_concurrency_limit(
    name: str = typer.Argument(
        ..., help="The name of the global concurrency limit to enable."
    ),
):
    """
    Enable a global concurrency limit.

    Arguments:
        name (str): The name of the global concurrency limit to enable.
    """
    async with get_client() as client:
        try:
            gcl_limit = await client.read_global_concurrency_limit_by_name(name=name)
            if gcl_limit.active:
                exit_with_error(
                    f"Global concurrency limit with name {name!r} is already enabled."
                )
            await client.update_global_concurrency_limit(
                name=name,
                concurrency_limit=GlobalConcurrencyLimitUpdate(active=True),
            )
        except ObjectNotFound:
            exit_with_error(f"Global concurrency limit {name!r} not found.")

    exit_with_success(f"Enabled global concurrency limit with name {name!r}.")


@global_concurrency_limit_app.command("disable")
async def disable_global_concurrency_limit(
    name: str = typer.Argument(
        ..., help="The name of the global concurrency limit to disable."
    ),
):
    """
    Disable a global concurrency limit.

    Arguments:
        name (str): The name of the global concurrency limit to disable.
    """
    async with get_client() as client:
        try:
            gcl_limit = await client.read_global_concurrency_limit_by_name(name=name)
            if not gcl_limit.active:
                exit_with_error(
                    f"Global concurrency limit with name {name!r} is already disabled."
                )
            await client.update_global_concurrency_limit(
                name=name,
                concurrency_limit=GlobalConcurrencyLimitUpdate(active=False),
            )
        except ObjectNotFound:
            exit_with_error(f"Global concurrency limit {name!r} not found.")

    exit_with_success(f"Disabled global concurrency limit with name {name!r}.")


@global_concurrency_limit_app.command("update")
async def update_global_concurrency_limit(
    name: str = typer.Argument(
        ..., help="The name of the global concurrency limit to update."
    ),
    enable: Optional[bool] = typer.Option(
        None, "--enable", help="Enable the global concurrency limit."
    ),
    disable: Optional[bool] = typer.Option(
        None, "--disable", help="Disable the global concurrency limit."
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-l", help="The limit of the global concurrency limit."
    ),
    active_slots: Optional[int] = typer.Option(
        None, "--active-slots", help="The number of active slots."
    ),
    slot_decay_per_second: Optional[float] = typer.Option(
        None, "--slot-decay-per-second", help="The slot decay per second."
    ),
):
    """
    Update a global concurrency limit.

    Arguments:
        name (str): The name of the global concurrency limit to update.
        enable (Optional[bool]): Enable the global concurrency limit.
        disable (Optional[bool]): Disable the global concurrency limit.
        limit (Optional[int]): The limit of the global concurrency limit.
        active_slots (Optional[int]): The number of active slots.
        slot_decay_per_second (Optional[float]): The slot decay per second.

    Examples:
        $ prefect global-concurrency-limit update my-gcl --limit 10
        $ prefect gcl update my-gcl --active-slots 5
        $ prefect gcl update my-gcl --slot-decay-per-second 0.5
        $ prefect gcl update my-gcl --enable
        $ prefect gcl update my-gcl --disable --limit 5
    """
    gcl = GlobalConcurrencyLimitUpdate()

    if enable and disable:
        exit_with_error(
            "Cannot enable and disable a global concurrency limit at the same time."
        )

    if enable:
        gcl.active = True
    if disable:
        gcl.active = False

    if limit is not None:
        gcl.limit = limit

    if active_slots is not None:
        gcl.active_slots = active_slots

    if slot_decay_per_second is not None:
        gcl.slot_decay_per_second = slot_decay_per_second

    if not gcl.model_dump(exclude_unset=True):
        exit_with_error("No update arguments provided.")

    try:
        GlobalConcurrencyLimitUpdate(**gcl.model_dump())
    except ValidationError as exc:
        exit_with_error(f"Invalid arguments provided: {exc}")
    except Exception as exc:
        exit_with_error(f"Error creating global concurrency limit: {exc}")

    async with get_client() as client:
        try:
            await client.update_global_concurrency_limit(
                name=name, concurrency_limit=gcl
            )
        except ObjectNotFound:
            exit_with_error(f"Global concurrency limit {name!r} not found.")
        except PrefectHTTPStatusError as exc:
            if exc.response.status_code == 422:
                parsed_response = exc.response.json()

                error_message = parsed_response["exception_detail"][0]["msg"]

                exit_with_error(
                    f"Error updating global concurrency limit: {error_message}"
                )

    exit_with_success(f"Updated global concurrency limit with name {name!r}.")


@global_concurrency_limit_app.command("create")
async def create_global_concurrency_limit(
    name: str = typer.Argument(
        ..., help="The name of the global concurrency limit to create."
    ),
    limit: int = typer.Option(
        ..., "--limit", "-l", help="The limit of the global concurrency limit."
    ),
    disable: Optional[bool] = typer.Option(
        None, "--disable", help="Create an inactive global concurrency limit."
    ),
    active_slots: Optional[int] = typer.Option(
        0, "--active-slots", help="The number of active slots."
    ),
    slot_decay_per_second: Optional[float] = typer.Option(
        0.0, "--slot-decay-per-second", help="The slot decay per second."
    ),
):
    """
    Create a global concurrency limit.

    Arguments:

        name (str): The name of the global concurrency limit to create.

        limit (int): The limit of the global concurrency limit.

        disable (Optional[bool]): Create an inactive global concurrency limit.

        active_slots (Optional[int]): The number of active slots.

        slot_decay_per_second (Optional[float]): The slot decay per second.

    Examples:

        $ prefect global-concurrency-limit create my-gcl --limit 10

        $ prefect gcl create my-gcl --limit 5 --active-slots 3

        $ prefect gcl create my-gcl --limit 5 --active-slots 3 --slot-decay-per-second 0.5

        $ prefect gcl create my-gcl --limit 5 --inactive
    """
    async with get_client() as client:
        try:
            await client.read_global_concurrency_limit_by_name(name=name)
        except ObjectNotFound:
            pass
        else:
            exit_with_error(
                f"Global concurrency limit {name!r} already exists. Please try creating with a different name."
            )

    try:
        gcl = GlobalConcurrencyLimitCreate(
            name=name,
            limit=limit,
            active=False if disable else True,
            active_slots=active_slots,
            slot_decay_per_second=slot_decay_per_second,
        )

    except ValidationError as exc:
        exit_with_error(f"Invalid arguments provided: {exc}")
    except Exception as exc:
        exit_with_error(f"Error creating global concurrency limit: {exc}")

    async with get_client() as client:
        try:
            gcl_id = await client.create_global_concurrency_limit(concurrency_limit=gcl)
        except PrefectHTTPStatusError as exc:
            parsed_response = exc.response.json()
            exc = parsed_response["exception_detail"][0]["msg"]

            exit_with_error(f"Error updating global concurrency limit: {exc}")

    exit_with_success(
        f"Created global concurrency limit with name {name!r} and ID '{gcl_id}'. Run `prefect gcl inspect {name}` to view details."
    )
