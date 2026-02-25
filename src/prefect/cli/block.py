"""
Block command — native cyclopts implementation.

Manage blocks and block types.
"""

from __future__ import annotations

import inspect
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Annotated, Any, Optional
from uuid import UUID

import cyclopts
import orjson
import yaml
from rich.table import Table

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

if TYPE_CHECKING:
    from prefect.client.schemas.objects import BlockDocument, BlockType

block_app: cyclopts.App = cyclopts.App(
    name="block",
    alias="blocks",
    help="Manage blocks.",
    version_flags=[],
    help_flags=["--help"],
)

block_type_app: cyclopts.App = cyclopts.App(
    name="type",
    alias="types",
    help="Inspect and delete block types.",
    version_flags=[],
    help_flags=["--help"],
)
block_app.command(block_type_app)


def _display_block(block_document: BlockDocument) -> Table:
    block_slug = (
        f"{getattr(block_document.block_type, 'slug', '')}/{block_document.name}"
    )
    block_table = Table(
        title=block_slug, show_header=False, show_footer=False, expand=True
    )
    block_table.add_column(style="italic cyan")
    block_table.add_column(style="blue")

    block_table.add_row("Block Type", getattr(block_document.block_type, "name", ""))
    block_table.add_row("Block id", str(block_document.id), end_section=True)
    for k, v in block_document.data.items():
        block_table.add_row(k, str(v))

    return block_table


def _display_block_type(block_type: BlockType) -> Table:
    block_type_table = Table(
        title=block_type.name, show_header=False, show_footer=False, expand=True
    )
    block_type_table.add_column(style="italic cyan")
    block_type_table.add_column(style="blue")

    block_type_table.add_row("Slug", block_type.slug)
    block_type_table.add_row("Block Type id", str(block_type.id))
    block_type_table.add_row(
        "Description",
        (
            block_type.description.splitlines()[0].partition(".")[0]
            if block_type.description is not None
            else ""
        ),
        end_section=True,
    )

    return block_type_table


def _display_block_schema_properties(block_schema_fields: dict[str, Any]) -> Table:
    required = block_schema_fields.get("required", [])
    properties = block_schema_fields.get("properties", {})

    block_schema_yaml_table = Table(
        title="Schema Properties",
        show_header=False,
        show_footer=False,
        show_lines=True,
        expand=True,
    )
    block_schema_yaml_table.add_column(style="cyan")
    block_schema_yaml_table.add_column()

    for property_name, property_schema in properties.items():
        if property_name in required:
            property_schema["required"] = True

        block_schema_yaml_table.add_row(
            property_name, yaml.dump(property_schema, default_flow_style=False)
        )

    return block_schema_yaml_table


def _display_block_schema_extra_definitions(
    block_schema_definitions: dict[str, Any],
) -> Table:
    extra_definitions_table = Table(
        title="Extra Definitions", show_header=False, show_footer=False, expand=True
    )
    extra_definitions_table.add_column(style="cyan")
    extra_definitions_table.add_column()
    extra_definitions_table.add_column()

    for definition_name, definition_schema in block_schema_definitions.items():
        for index, (property_name, property_schema) in enumerate(
            definition_schema.get("properties", {}).items()
        ):
            extra_definitions_table.add_row(
                definition_name if index == 0 else None,
                property_name,
                yaml.dump(property_schema, default_flow_style=False),
            )

    return extra_definitions_table


async def _register_blocks_in_module(module: ModuleType) -> list[type]:
    from prefect.blocks.core import Block, InvalidBlockRegistration

    registered_blocks: list[type[Block]] = []
    for _, cls in inspect.getmembers(module):
        if cls is not None and Block.is_block_class(cls):
            try:
                coro = cls.register_type_and_schema()
                if TYPE_CHECKING:
                    assert inspect.isawaitable(coro)
                await coro
                registered_blocks.append(cls)
            except InvalidBlockRegistration:
                pass
    return registered_blocks


def _build_registered_blocks_table(registered_blocks: list[type]) -> Table:
    table = Table("Registered Blocks")
    for block in registered_blocks:
        table.add_row(block.get_block_type_name())
    return table


@block_app.command(name="register")
@with_cli_exception_handling
async def register(
    *,
    module_name: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--module",
            alias="-m",
            help="Python module containing block types to be registered",
        ),
    ] = None,
    file_path: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--file",
            alias="-f",
            help="Path to .py file containing block types to be registered",
        ),
    ] = None,
):
    """Register blocks types within a module or file.

    This makes the blocks available for configuration via the UI.
    If a block type has already been registered, its registration will be updated to
    match the block's current definition.
    """
    from prefect.client.base import ServerType, determine_server_type
    from prefect.exceptions import ScriptError, exception_traceback
    from prefect.settings import get_current_settings
    from prefect.utilities.asyncutils import run_sync_in_worker_thread
    from prefect.utilities.importtools import load_script_as_module

    if not (bool(file_path) ^ bool(module_name)):
        exit_with_error(
            "Please specify either a module or a file containing blocks to be"
            " registered, but not both."
        )

    imported_module: Optional[ModuleType] = None
    if module_name:
        try:
            imported_module = import_module(name=module_name)
        except ModuleNotFoundError:
            exit_with_error(
                f"Unable to load {module_name}. Please make sure the module is "
                "installed in your current environment."
            )

    if file_path:
        path = Path(file_path)
        if path.suffix != ".py":
            exit_with_error(
                f"{file_path} is not a .py file. Please specify a "
                ".py that contains blocks to be registered."
            )
        try:
            imported_module = await run_sync_in_worker_thread(
                load_script_as_module, str(path)
            )
        except ScriptError as exc:
            _cli.console.print(exc)
            _cli.console.print(exception_traceback(exc.user_exc))
            exit_with_error(
                f"Unable to load file at {file_path}. Please make sure the file path "
                "is correct and the file contains valid Python."
            )

    if TYPE_CHECKING:
        assert imported_module is not None
    registered_blocks = await _register_blocks_in_module(imported_module)
    number_of_registered_blocks = len(registered_blocks)

    if number_of_registered_blocks == 0:
        source = f"module {module_name!r}" if module_name else f"file {file_path!r}"
        exit_with_error(
            f"No blocks were registered from {source}.\n\nPlease make sure the {source} "
            "contains valid blocks.\n"
        )

    block_text = "block" if 0 < number_of_registered_blocks < 2 else "blocks"
    _cli.console.print(
        f"[green]Successfully registered {number_of_registered_blocks} {block_text}\n"
    )
    _cli.console.print(_build_registered_blocks_table(registered_blocks))
    msg = (
        "\n To configure the newly registered blocks, "
        "go to the Blocks page in the Prefect UI.\n"
    )

    if ui_url := get_current_settings().ui_url:
        if determine_server_type() == ServerType.CLOUD:
            block_catalog_url = f"{ui_url}/settings/blocks/catalog"
        else:
            block_catalog_url = f"{ui_url}/blocks/catalog"
        msg = f"{msg.rstrip().rstrip('.')}: {block_catalog_url}\n"

    _cli.console.print(msg, soft_wrap=True)


@block_app.command(name="ls")
@with_cli_exception_handling
async def block_ls(
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
    """View all configured blocks."""
    from prefect.client.orchestration import get_client

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")
    async with get_client() as client:
        blocks = await client.read_block_documents()
    if output and output.lower() == "json":
        blocks_json = [block.model_dump(mode="json") for block in blocks]
        json_output = orjson.dumps(blocks_json, option=orjson.OPT_INDENT_2).decode()
        _cli.console.print(json_output)
    else:
        table = Table(
            title="Blocks", caption="List Block Types using `prefect block type ls`"
        )
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Type", style="blue", no_wrap=True)
        table.add_column("Name", style="blue", no_wrap=True)
        table.add_column("Slug", style="blue", no_wrap=True)

        for block in sorted(
            blocks, key=lambda x: f"{getattr(x.block_type, 'slug', '')}/{x.name}"
        ):
            table.add_row(
                str(block.id),
                getattr(block.block_type, "name", ""),
                str(block.name),
                f"{getattr(block.block_type, 'slug', '')}/{block.name}",
            )

        _cli.console.print(table)


@block_app.command(name="delete")
@with_cli_exception_handling
async def block_delete(
    slug: Annotated[
        Optional[str],
        cyclopts.Parameter(
            help="A block slug. Formatted as '<BLOCK_TYPE_SLUG>/<BLOCK_NAME>'"
        ),
    ] = None,
    *,
    block_id: Annotated[
        Optional[UUID],
        cyclopts.Parameter("--id", help="A block id."),
    ] = None,
):
    """Delete a configured block."""
    from prefect.cli._prompts import confirm
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    async with get_client() as client:
        if slug is None and block_id is not None:
            try:
                if _cli.is_interactive() and not confirm(
                    f"Are you sure you want to delete block with id {block_id!r}?",
                    default=False,
                    console=_cli.console,
                ):
                    exit_with_error("Deletion aborted.")
                await client.delete_block_document(block_id)
                exit_with_success(f"Deleted Block '{block_id}'.")
            except ObjectNotFound:
                exit_with_error(f"Block {block_id!r} not found!")
        elif slug is not None:
            if "/" not in slug:
                exit_with_error(
                    f"{slug!r} is not valid. Slug must contain a '/', e.g. 'json/my-json-block'"
                )
            block_type_slug, block_document_name = slug.split("/")
            try:
                block_document = await client.read_block_document_by_name(
                    block_document_name, block_type_slug, include_secrets=False
                )
                if _cli.is_interactive() and not confirm(
                    f"Are you sure you want to delete block with slug {slug!r}?",
                    default=False,
                    console=_cli.console,
                ):
                    exit_with_error("Deletion aborted.")
                await client.delete_block_document(block_document.id)
                exit_with_success(f"Deleted Block '{slug}'.")
            except ObjectNotFound:
                exit_with_error(f"Block {slug!r} not found!")
        else:
            exit_with_error("Must provide a block slug or id")


@block_app.command(name="create")
@with_cli_exception_handling
async def block_create(
    block_type_slug: Annotated[
        str,
        cyclopts.Parameter(
            help="A block type slug. View available types with: prefect block type ls",
            show_default=False,
        ),
    ],
):
    """Generate a link to the Prefect UI to create a block."""
    from prefect.client.base import ServerType, determine_server_type
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound
    from prefect.settings import get_current_settings

    async with get_client() as client:
        try:
            block_type = await client.read_block_type_by_slug(block_type_slug)
        except ObjectNotFound:
            _cli.console.print(f"[red]Block type {block_type_slug!r} not found![/red]")
            block_types = await client.read_block_types()
            slugs = {bt.slug for bt in block_types}
            _cli.console.print(f"Available block types: {', '.join(slugs)}")
            raise SystemExit(1)

        ui_url = get_current_settings().ui_url
        if not ui_url:
            exit_with_error(
                "Prefect must be configured to use a hosted Prefect server or "
                "Prefect Cloud to display the Prefect UI"
            )
        if determine_server_type() == ServerType.CLOUD:
            block_link = f"{ui_url}/settings/blocks/catalog/{block_type.slug}/create"
        else:
            block_link = f"{ui_url}/blocks/catalog/{block_type.slug}/create"
        _cli.console.print(
            f"Create a {block_type_slug} block: {block_link}",
        )


@block_app.command(name="inspect")
@with_cli_exception_handling
async def block_inspect(
    slug: Annotated[
        Optional[str],
        cyclopts.Parameter(help="A Block slug: <BLOCK_TYPE_SLUG>/<BLOCK_NAME>"),
    ] = None,
    *,
    block_id: Annotated[
        Optional[UUID],
        cyclopts.Parameter("--id", help="A Block id to search for if no slug is given"),
    ] = None,
):
    """Displays details about a configured block."""
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    async with get_client() as client:
        if slug is None and block_id is not None:
            try:
                block_document = await client.read_block_document(
                    block_id, include_secrets=False
                )
            except ObjectNotFound:
                exit_with_error(f"Block {block_id!r} not found!")
        elif slug is not None:
            if "/" not in slug:
                exit_with_error(
                    f"{slug!r} is not valid. Slug must contain a '/', e.g. 'json/my-json-block'"
                )
            block_type_slug, block_document_name = slug.split("/")
            try:
                block_document = await client.read_block_document_by_name(
                    block_document_name, block_type_slug, include_secrets=False
                )
            except ObjectNotFound:
                exit_with_error(f"Block {slug!r} not found!")
        else:
            exit_with_error("Must provide a block slug or id")
        _cli.console.print(_display_block(block_document))


# =========================================================================
# Block Type subcommands
# =========================================================================


@block_type_app.command(name="ls")
@with_cli_exception_handling
async def list_types(
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
    """List all block types."""
    from prefect.client.orchestration import get_client

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")
    async with get_client() as client:
        block_types = await client.read_block_types()
    if output and output.lower() == "json":
        block_types_json = [
            block_type.model_dump(mode="json") for block_type in block_types
        ]
        json_output = orjson.dumps(
            block_types_json, option=orjson.OPT_INDENT_2
        ).decode()
        _cli.console.print(json_output)
    else:
        table = Table(
            title="Block Types",
            show_lines=True,
        )

        table.add_column("Block Type Slug", style="italic cyan", no_wrap=True)
        table.add_column("Description", style="blue", no_wrap=False, justify="left")
        table.add_column(
            "Generate creation link", style="italic cyan", no_wrap=False, justify="left"
        )

        for blocktype in sorted(block_types, key=lambda x: x.name):
            table.add_row(
                str(blocktype.slug),
                (
                    str(blocktype.description.splitlines()[0].partition(".")[0])
                    if blocktype.description is not None
                    else ""
                ),
                f"prefect block create {blocktype.slug}",
            )

        _cli.console.print(table)


@block_type_app.command(name="inspect")
@with_cli_exception_handling
async def blocktype_inspect(
    slug: Annotated[str, cyclopts.Parameter(help="A block type slug")],
):
    """Display details about a block type."""
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    async with get_client() as client:
        try:
            block_type = await client.read_block_type_by_slug(slug)
        except ObjectNotFound:
            exit_with_error(f"Block type {slug!r} not found!")

        _cli.console.print(_display_block_type(block_type))

        try:
            latest_schema = await client.get_most_recent_block_schema_for_block_type(
                block_type.id
            )
        except Exception:
            exit_with_error(f"Failed to fetch latest schema for the {slug} block type")

        if latest_schema is None:
            exit_with_error(f"No schema found for the {slug} block type")

        _cli.console.print(_display_block_schema_properties(latest_schema.fields))

        latest_schema_extra_definitions = latest_schema.fields.get("definitions")
        if latest_schema_extra_definitions:
            _cli.console.print(
                _display_block_schema_extra_definitions(latest_schema_extra_definitions)
            )


@block_type_app.command(name="delete")
@with_cli_exception_handling
async def blocktype_delete(
    slug: Annotated[str, cyclopts.Parameter(help="A Block type slug")],
):
    """Delete an unprotected Block Type."""
    from prefect.cli._prompts import confirm
    from prefect.client.orchestration import get_client
    from prefect.exceptions import (
        ObjectNotFound,
        PrefectHTTPStatusError,
        ProtectedBlockError,
    )

    async with get_client() as client:
        try:
            block_type = await client.read_block_type_by_slug(slug)
            if _cli.is_interactive() and not confirm(
                f"Are you sure you want to delete block type {block_type.slug!r}?",
                default=False,
                console=_cli.console,
            ):
                exit_with_error("Deletion aborted.")
            await client.delete_block_type(block_type.id)
            exit_with_success(f"Deleted Block Type '{slug}'.")
        except ObjectNotFound:
            exit_with_error(f"Block Type {slug!r} not found!")
        except ProtectedBlockError:
            exit_with_error(f"Block Type {slug!r} is a protected block!")
        except PrefectHTTPStatusError:
            exit_with_error(f"Cannot delete Block Type {slug!r}!")
