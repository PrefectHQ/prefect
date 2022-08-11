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
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.client import get_client
from prefect.exceptions import ScriptError, exception_traceback
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.importtools import load_script_as_module

blocks_app = PrefectTyper(name="block", help="Commands for working with blocks.")
blocktypes_app = PrefectTyper(name="type", help="Commands for working with blocks.")
app.add_typer(blocks_app, aliases=["blocks"])
blocks_app.add_typer(blocktypes_app, aliases=["types"])


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
        None, "--module", "-m", help="Python module containing blocks to be registered"
    ),
    file_path: Optional[Path] = typer.Option(
        None, "--file", "-f", help="Path to .py file containing blocks to be registered"
    ),
):
    """
    Register blocks within a module or file to be available for configuration via the UI.
    If a block has already been registered, its registration will be updated to match the
    block's current definition.

    \b
    Examples:
        \b
        Register blocks in a Python module:
        $ prefect block register -m prefect_aws.credentials
        \b
        Register blocks in a .py file:
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


@blocks_app.command()
async def ls():
    """
    View all configured Blocks.
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


@blocktypes_app.command("ls")
async def list_types():
    """
    View all Block types.
    """
    async with get_client() as client:
        block_types = await client.read_block_types()

    table = Table(
        title="Block Types",
        show_lines=True,
    )
    table.add_column("Name", style="blue", no_wrap=True)
    table.add_column("Slug", style="italic cyan", no_wrap=True)
    table.add_column("Description", style="blue", no_wrap=False, justify="right")

    for blocktype in sorted(block_types, key=lambda x: x.name):
        table.add_row(
            str(blocktype.name),
            str(blocktype.slug),
            str(blocktype.description.splitlines()[0].partition(".")[0])
            if blocktype.description is not None
            else "",
        )

    app.console.print(table)
