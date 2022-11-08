"""
Command line interface for working with blocks.
"""
import inspect
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import List, Optional, Type

import typer
from rich.table import Table

from prefect.blocks.core import Block, InvalidBlockRegistration
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client import get_client
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

blocks_app = PrefectTyper(name="block", help="Commands for working with blocks.")
blocktypes_app = PrefectTyper(
    name="type", help="Commands for working with blocks types."
)
app.add_typer(blocks_app, aliases=["blocks"])
blocks_app.add_typer(blocktypes_app, aliases=["types"])


def display_block(block_document):
    block_slug = f"{block_document.block_type.slug}/{block_document.name}"
    block_table = Table(
        title=block_slug, show_header=False, show_footer=False, expand=True
    )
    block_table.add_column(style="italic cyan")
    block_table.add_column(style="blue")

    block_table.add_row("Block Type", block_document.block_type.name)
    block_table.add_row("Block id", str(block_document.id), end_section=True)
    for k, v in block_document.data.items():
        block_table.add_row(k, str(v))

    return block_table


def display_block_type(block_type):
    block_type_table = Table(
        title=block_type.name, show_header=False, show_footer=False, expand=True
    )
    block_type_table.add_column(style="italic cyan")
    block_type_table.add_column(style="blue")

    block_type_table.add_row("Slug", block_type.slug)
    block_type_table.add_row("Block Type id", str(block_type.id))
    block_type_table.add_row(
        "Description",
        block_type.description.splitlines()[0].partition(".")[0]
        if block_type.description is not None
        else "",
        end_section=True,
    )

    return block_type_table


async def _register_blocks_in_module(module: ModuleType) -> List[Type[Block]]:
    registered_blocks = []
    for _, cls in inspect.getmembers(module):
        if Block.is_block_class(cls):
            try:
                await cls.register_type_and_schema()
                registered_blocks.append(cls)
            except InvalidBlockRegistration:
                # Attempted to register Block base class or a Block interface
                pass
    return registered_blocks


def _build_registered_blocks_table(registered_blocks: List[Type[Block]]):
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
            "Please specify either a module or a file containing blocks to be registered, but not both."
        )

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

    registered_blocks = await _register_blocks_in_module(imported_module)
    number_of_registered_blocks = len(registered_blocks)
    block_text = "block" if 0 < number_of_registered_blocks < 2 else "blocks"
    app.console.print(
        f"[green]Successfully registered {number_of_registered_blocks} {block_text}\n"
    )
    app.console.print(_build_registered_blocks_table(registered_blocks))
    app.console.print(
        "\n To configure the newly registered blocks, "
        "go to the Blocks page in the Prefect UI.\n"
    )


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

    for block in sorted(blocks, key=lambda x: f"{x.block_type.slug}/{x.name}"):
        table.add_row(
            str(block.id),
            block.block_type.name,
            str(block.name),
            f"{block.block_type.slug}/{block.name}",
        )

    app.console.print(table)


@blocks_app.command("delete")
async def block_delete(
    slug: Optional[str] = typer.Argument(
        None, help="A block slug. Formatted as '<BLOCK_TYPE_SLUG>/<BLOCK_NAME>'"
    ),
    block_id: Optional[str] = typer.Option(None, "--id", help="A block id."),
):
    """
    Delete a configured block.
    """
    async with get_client() as client:
        if slug is None and block_id is not None:
            try:
                await client.delete_block_document(block_id)
                exit_with_success(f"Deleted Block '{block_id}'.")
            except ObjectNotFound:
                exit_with_error(f"Deployment {block_id!r} not found!")
        elif slug is not None:
            block_type_slug, block_document_name = slug.split("/")
            try:
                block_document = await client.read_block_document_by_name(
                    block_document_name, block_type_slug, include_secrets=False
                )
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
                "Prefect must be configured to use a hosted Orion server or "
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
    block_id: Optional[str] = typer.Option(
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
                exit_with_error(f"Deployment {block_id!r} not found!")
        elif slug is not None:
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
            str(blocktype.description.splitlines()[0].partition(".")[0])
            if blocktype.description is not None
            else "",
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
            await client.delete_block_type(block_type.id)
            exit_with_success(f"Deleted Block Type '{slug}'.")
        except ObjectNotFound:
            exit_with_error(f"Block Type {slug!r} not found!")
        except ProtectedBlockError:
            exit_with_error(f"Block Type {slug!r} is a protected block!")
        except PrefectHTTPStatusError:
            exit_with_error(f"Cannot delete Block Type {slug!r}!")
