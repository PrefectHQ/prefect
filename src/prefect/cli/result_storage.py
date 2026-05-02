"""
Manage default result storage.
"""

from typing import Annotated, Any, Optional
from uuid import UUID

import cyclopts
import orjson
from rich.table import Table

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)
from prefect.exceptions import ObjectNotFound

result_storage_app: cyclopts.App = cyclopts.App(
    name="result-storage", help="Manage default result storage."
)


def _display_default_result_storage(
    default_result_storage_block_id: UUID,
    block_slug: str | None,
) -> Table:
    storage_table = Table(show_header=True, header_style="bold")
    storage_table.add_column("Setting", style="cyan")
    storage_table.add_column("Value")
    storage_table.add_row(
        "default_result_storage_block_id", str(default_result_storage_block_id)
    )
    if block_slug is not None:
        storage_table.add_row("block", block_slug)
    return storage_table


async def _read_block_slug(client: Any, block_document_id: UUID) -> str | None:
    try:
        block_document = await client.read_block_document(
            block_document_id, include_secrets=False
        )
    except ObjectNotFound:
        return None

    block_type_slug = getattr(block_document.block_type, "slug", None)
    if block_type_slug is None:
        return block_document.name
    return f"{block_type_slug}/{block_document.name}"


async def _resolve_block_document_id(
    client: Any,
    block: str | None,
    block_id: UUID | None,
) -> UUID:
    if block is None and block_id is None:
        exit_with_error("Must provide a block slug or id.")
    if block is not None and block_id is not None:
        exit_with_error("Provide either a block slug or id, not both.")
    if block_id is not None:
        return block_id

    assert block is not None
    if "/" not in block:
        exit_with_error(
            f"{block!r} is not valid. Slug must contain a '/', e.g. "
            "'local-file-system/my-results'."
        )

    block_type_slug, block_document_name = block.split("/", 1)
    try:
        block_document = await client.read_block_document_by_name(
            block_document_name,
            block_type_slug,
            include_secrets=False,
        )
    except ObjectNotFound:
        exit_with_error(f"Block {block!r} not found!")

    return block_document.id


@result_storage_app.command(name="inspect")
@with_cli_exception_handling
async def result_storage_inspect(
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
    """Inspect the configured default result storage."""
    from prefect.client.orchestration import get_client

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    async with get_client() as client:
        configuration = await client.read_server_default_result_storage()
        block_document_id = configuration.default_result_storage_block_id

        if block_document_id is None:
            if output and output.lower() == "json":
                _cli.console.print(
                    orjson.dumps(
                        {"default_result_storage_block_id": None},
                        option=orjson.OPT_INDENT_2,
                    ).decode(),
                    soft_wrap=True,
                )
            else:
                _cli.console.print("No default result storage is configured.")
            return

        block_slug = await _read_block_slug(client, block_document_id)
        if output and output.lower() == "json":
            _cli.console.print(
                orjson.dumps(
                    {
                        "default_result_storage_block_id": str(block_document_id),
                        "block": block_slug,
                    },
                    option=orjson.OPT_INDENT_2,
                ).decode(),
                soft_wrap=True,
            )
        else:
            _cli.console.print(
                _display_default_result_storage(block_document_id, block_slug)
            )


@result_storage_app.command(name="set")
@with_cli_exception_handling
async def result_storage_set(
    block: Annotated[
        Optional[str],
        cyclopts.Parameter(
            help="A block slug in the form <BLOCK_TYPE_SLUG>/<BLOCK_NAME>."
        ),
    ] = None,
    *,
    block_id: Annotated[
        Optional[UUID],
        cyclopts.Parameter("--id", help="A block document id."),
    ] = None,
):
    """Set the default result storage block."""
    from prefect.client.orchestration import get_client

    async with get_client() as client:
        block_document_id = await _resolve_block_document_id(client, block, block_id)
        await client.update_server_default_result_storage(block_document_id)

    exit_with_success("Set default result storage.")


@result_storage_app.command(name="clear")
@with_cli_exception_handling
async def result_storage_clear():
    """Clear the configured default result storage."""
    from prefect.client.orchestration import get_client

    async with get_client() as client:
        await client.clear_server_default_result_storage()

    exit_with_success("Cleared default result storage.")
