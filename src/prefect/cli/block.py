"""
Command line interface for working with blocks.
"""

from __future__ import annotations

import inspect
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

import typer
import yaml
from rich.table import Table

from prefect.blocks.core import Block, InvalidBlockRegistration
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app, is_interactive
from prefect.client.orchestration import get_client
from prefect.exceptions import (
    ObjectNotFound,
    PrefectHTTPStatusError,
    ProtectedBlockError,
    ScriptError,
    exception_traceback,
)
from prefect.settings import PREFECT_UI_URL
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.importtools import load_script_as_module

if TYPE_CHECKING:
    from prefect.client.schemas.objects import BlockDocument, BlockType

blocks_app: PrefectTyper = PrefectTyper(name="block", help="Manage blocks.")
blocktypes_app: PrefectTyper = PrefectTyper(
    name="type", help="Inspect and delete block types."
)
app.add_typer(blocks_app, aliases=["blocks"])
blocks_app.add_typer(blocktypes_app, aliases=["types"])


def display_block(block_document: "BlockDocument") -> Table:
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


def display_block_type(block_type: "BlockType") -> Table:
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


def display_block_schema_properties(block_schema_fields: dict[str, Any]) -> Table:
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


def display_block_schema_extra_definitions(
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
            # We'll set the definition column for the first row of each group only
            # to give visual whitespace between each group
            extra_definitions_table.add_row(
                definition_name if index == 0 else None,
                property_name,
                yaml.dump(property_schema, default_flow_style=False),
            )

    return extra_definitions_table


async def _register_blocks_in_module(module: ModuleType) -> list[type[Block]]:
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
                # Attempted to register Block base class or a Block interface
                pass
    return registered_blocks


def _build_registered_blocks_table(registered_blocks: list[type[Block]]) -> Table:
    table = Table("Registered Blocks")
    for block in registered_blocks:
        table.add_row(block.get_block_type_name())
    return table


@blocks_app.command()
async def register(
    module_name: Optional[str] = typer.Option(
        None,
        "--module",
        "-m",
        help="Python module containing block types to be registered",
    ),
    file_path: Optional[Path] = typer.Option(
        None,
        "--file",
        "-f",
        help="Path to .py file containing block types to be registered",
    ),
):
    """
    Register blocks types within a module or file.

    This makes the blocks available for configuration via the UI.
    If a block type has already been registered, its registration will be updated to
    match the block's current definition.

    \b
    Examples:
        \b
        Register block types in a Python module:
        $ prefect block register -m prefect_aws.credentials
        \b
        Register block types in a .py file:
        $ prefect block register -f my_blocks.py
    """
    # Handles if both options are specified or if neither are specified
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
        if file_path.suffix != ".py":
            exit_with_error(
                f"{file_path} is not a .py file. Please specify a "
                ".py that contains blocks to be registered."
            )
        try:
            imported_module = await run_sync_in_worker_thread(
                load_script_as_module, str(file_path)
            )
        except ScriptError as exc:
            app.console.print(exc)
            app.console.print(exception_traceback(exc.user_exc))
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
    app.console.print(
        f"[green]Successfully registered {number_of_registered_blocks} {block_text}\n"
    )
    app.console.print(_build_registered_blocks_table(registered_blocks))
    msg = (
        "\n To configure the newly registered blocks, "
        "go to the Blocks page in the Prefect UI.\n"
    )

    if ui_url := PREFECT_UI_URL:
        block_catalog_url = f"{ui_url}/blocks/catalog"
        msg = f"{msg.rstrip().rstrip('.')}: {block_catalog_url}\n"

    app.console.print(msg, soft_wrap=True)


@blocks_app.command("ls")
async def block_ls():
    """
    View all configured blocks.
    """
    async with get_client() as client:
        blocks = await client.read_block_documents()

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

    app.console.print(table)


@blocks_app.command("delete")
async def block_delete(
    slug: Optional[str] = typer.Argument(
        None, help="A block slug. Formatted as '<BLOCK_TYPE_SLUG>/<BLOCK_NAME>'"
    ),
    block_id: Optional[UUID] = typer.Option(None, "--id", help="A block id."),
):
    """
    Delete a configured block.
    """
    async with get_client() as client:
        if slug is None and block_id is not None:
            try:
                if is_interactive() and not typer.confirm(
                    (f"Are you sure you want to delete block with id {block_id!r}?"),
                    default=False,
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
                if is_interactive() and not typer.confirm(
                    (f"Are you sure you want to delete block with slug {slug!r}?"),
                    default=False,
                ):
                    exit_with_error("Deletion aborted.")
                await client.delete_block_document(block_document.id)
                exit_with_success(f"Deleted Block '{slug}'.")
            except ObjectNotFound:
                exit_with_error(f"Block {slug!r} not found!")
        else:
            exit_with_error("Must provide a block slug or id")


@blocks_app.command("create")
async def block_create(
    block_type_slug: str = typer.Argument(
        ...,
        help="A block type slug. View available types with: prefect block type ls",
        show_default=False,
    ),
):
    """
    Generate a link to the Prefect UI to create a block.
    """
    async with get_client() as client:
        try:
            block_type = await client.read_block_type_by_slug(block_type_slug)
        except ObjectNotFound:
            app.console.print(f"[red]Block type {block_type_slug!r} not found![/red]")
            block_types = await client.read_block_types()
            slugs = {block_type.slug for block_type in block_types}
            app.console.print(f"Available block types: {', '.join(slugs)}")
            raise typer.Exit(1)

        if not PREFECT_UI_URL:
            exit_with_error(
                "Prefect must be configured to use a hosted Prefect server or "
                "Prefect Cloud to display the Prefect UI"
            )

        block_link = f"{PREFECT_UI_URL.value()}/blocks/catalog/{block_type.slug}/create"
        app.console.print(
            f"Create a {block_type_slug} block: {block_link}",
        )


@blocks_app.command("inspect")
async def block_inspect(
    slug: Optional[str] = typer.Argument(
        None, help="A Block slug: <BLOCK_TYPE_SLUG>/<BLOCK_NAME>"
    ),
    block_id: Optional[UUID] = typer.Option(
        None, "--id", help="A Block id to search for if no slug is given"
    ),
):
    """
    Displays details about a configured block.
    """
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
        app.console.print(display_block(block_document))


@blocktypes_app.command("ls")
async def list_types():
    """
    List all block types.
    """
    async with get_client() as client:
        block_types = await client.read_block_types()

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

    app.console.print(table)


@blocktypes_app.command("inspect")
async def blocktype_inspect(
    slug: str = typer.Argument(..., help="A block type slug"),
):
    """
    Display details about a block type.
    """
    async with get_client() as client:
        try:
            block_type = await client.read_block_type_by_slug(slug)
        except ObjectNotFound:
            exit_with_error(f"Block type {slug!r} not found!")

        app.console.print(display_block_type(block_type))

        try:
            latest_schema = await client.get_most_recent_block_schema_for_block_type(
                block_type.id
            )
        except Exception:
            exit_with_error(f"Failed to fetch latest schema for the {slug} block type")

        if latest_schema is None:
            exit_with_error(f"No schema found for the {slug} block type")

        app.console.print(display_block_schema_properties(latest_schema.fields))

        latest_schema_extra_definitions = latest_schema.fields.get("definitions")
        if latest_schema_extra_definitions:
            app.console.print(
                display_block_schema_extra_definitions(latest_schema_extra_definitions)
            )


@blocktypes_app.command("delete")
async def blocktype_delete(
    slug: str = typer.Argument(..., help="A Block type slug"),
):
    """
    Delete an unprotected Block Type.
    """
    async with get_client() as client:
        try:
            block_type = await client.read_block_type_by_slug(slug)
            if is_interactive() and not typer.confirm(
                (f"Are you sure you want to delete block type {block_type.slug!r}?"),
                default=False,
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
