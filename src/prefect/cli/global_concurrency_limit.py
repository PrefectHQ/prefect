"""
Global-concurrency-limit command — native cyclopts implementation.

Manage global concurrency limits.
"""

from pathlib import Path
from typing import Annotated, Optional

import cyclopts

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

global_concurrency_limit_app: cyclopts.App = cyclopts.App(
    name="global-concurrency-limit",
    alias="gcl",
    help="Manage global concurrency limits.",
    version_flags=[],
    help_flags=["--help"],
)


@global_concurrency_limit_app.command(name="ls")
@with_cli_exception_handling
async def ls(
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
    """List all global concurrency limits."""
    import orjson
    from rich.table import Table

    from prefect.client.orchestration import get_client
    from prefect.types._datetime import human_friendly_diff

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    async with get_client() as client:
        gcl_limits = await client.read_global_concurrency_limits(limit=100, offset=0)
        if not gcl_limits and not output:
            exit_with_success("No global concurrency limits found.")

    if output and output.lower() == "json":
        gcl_limits_json = [
            gcl_limit.model_dump(mode="json") for gcl_limit in gcl_limits
        ]
        json_output = orjson.dumps(gcl_limits_json, option=orjson.OPT_INDENT_2).decode()
        _cli.console.print(json_output)
    else:
        table = Table(
            title="Global Concurrency Limits",
            caption="List Global Concurrency Limits using `prefect global-concurrency-limit ls`",
            show_header=True,
        )

        table.add_column(
            "ID", justify="right", style="cyan", no_wrap=True, overflow="fold"
        )
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

        _cli.console.print(table)


@global_concurrency_limit_app.command(name="inspect")
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
    file_path: Annotated[
        Optional[Path],
        cyclopts.Parameter(
            "--file",
            alias="-f",
            help="Path to .json file to write the global concurrency limit output to.",
        ),
    ] = None,
):
    """Inspect a global concurrency limit."""
    import orjson
    from rich.pretty import Pretty

    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

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
            _cli.console.print(json_output)
        else:
            with open(file_path, "w") as f:
                f.write(json_output)
                exit_with_success(
                    f"Global concurrency limit {name!r} written to {file_path}"
                )
    else:
        _cli.console.print(Pretty(gcl_limit))


@global_concurrency_limit_app.command(name="delete")
@with_cli_exception_handling
async def delete(name: str):
    """Delete a global concurrency limit."""
    from prefect.cli._prompts import confirm
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    async with get_client() as client:
        try:
            gcl_limit = await client.read_global_concurrency_limit_by_name(name=name)

            if _cli.is_interactive() and not confirm(
                f"Are you sure you want to delete global concurrency limit with name {gcl_limit.name!r}?",
                default=False,
                console=_cli.console,
            ):
                exit_with_error("Deletion aborted.")

            await client.delete_global_concurrency_limit_by_name(name=name)
        except ObjectNotFound:
            exit_with_error(f"Global concurrency limit {name!r} not found.")

    exit_with_success(f"Deleted global concurrency limit with name {name!r}.")


@global_concurrency_limit_app.command(name="enable")
@with_cli_exception_handling
async def enable(name: str):
    """Enable a global concurrency limit."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import GlobalConcurrencyLimitUpdate
    from prefect.exceptions import ObjectNotFound

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


@global_concurrency_limit_app.command(name="disable")
@with_cli_exception_handling
async def disable(name: str):
    """Disable a global concurrency limit."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import GlobalConcurrencyLimitUpdate
    from prefect.exceptions import ObjectNotFound

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


@global_concurrency_limit_app.command(name="update")
@with_cli_exception_handling
async def update(
    name: str,
    *,
    enable: Annotated[
        Optional[bool],
        cyclopts.Parameter("--enable", help="Enable the global concurrency limit."),
    ] = None,
    disable: Annotated[
        Optional[bool],
        cyclopts.Parameter("--disable", help="Disable the global concurrency limit."),
    ] = None,
    limit: Annotated[
        Optional[int],
        cyclopts.Parameter(
            "--limit", alias="-l", help="The limit of the global concurrency limit."
        ),
    ] = None,
    active_slots: Annotated[
        Optional[int],
        cyclopts.Parameter("--active-slots", help="The number of active slots."),
    ] = None,
    slot_decay_per_second: Annotated[
        Optional[float],
        cyclopts.Parameter(
            "--slot-decay-per-second", help="The slot decay per second."
        ),
    ] = None,
):
    """Update a global concurrency limit."""
    from pydantic import ValidationError

    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import GlobalConcurrencyLimitUpdate
    from prefect.exceptions import ObjectNotFound, PrefectHTTPStatusError

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


@global_concurrency_limit_app.command(name="create")
@with_cli_exception_handling
async def create(
    name: str,
    *,
    limit: Annotated[
        int,
        cyclopts.Parameter(
            "--limit", alias="-l", help="The limit of the global concurrency limit."
        ),
    ],
    disable: Annotated[
        Optional[bool],
        cyclopts.Parameter(
            "--disable", help="Create an inactive global concurrency limit."
        ),
    ] = None,
    active_slots: Annotated[
        Optional[int],
        cyclopts.Parameter("--active-slots", help="The number of active slots."),
    ] = 0,
    slot_decay_per_second: Annotated[
        Optional[float],
        cyclopts.Parameter(
            "--slot-decay-per-second", help="The slot decay per second."
        ),
    ] = 0.0,
):
    """Create a global concurrency limit."""
    from pydantic import ValidationError

    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import GlobalConcurrencyLimitCreate
    from prefect.exceptions import ObjectNotFound, PrefectHTTPStatusError

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
