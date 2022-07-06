"""
Command line interface for managing storage settings
"""
import textwrap
from itertools import filterfalse
from uuid import UUID

import typer
from rich.emoji import Emoji
from rich.table import Table

from prefect.blocks.core import Block
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client import get_client
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound

storage_config_app = PrefectTyper(
    name="storage",
    help="Commands for managing storage settings.",
)
app.add_typer(storage_config_app)

JSON_TO_PY_TYPES = {"string": str}
JSON_TO_PY_EMPTY = {"string": "NOT-PROVIDED"}


@storage_config_app.command()
async def create():
    """Create a new storage configuration."""
    async with get_client() as client:
        schemas = await client.read_block_schemas()
    unconfigurable = set()

    # KV Server Storage is for internal use only and should not be exposed to users
    schemas = list(
        filterfalse(lambda s: s.block_type.name == "KV Server Storage", schemas)
    )

    # filter out blocks without the storage capability
    schemas = list(filterfalse(lambda s: "storage" not in s.capabilities, schemas))

    for schema in schemas:
        for property, property_spec in schema.fields["properties"].items():
            if (
                property_spec["type"] == "object"
                and property in schema.fields["required"]
            ):
                unconfigurable.add(schema)

    for schema in unconfigurable:
        schemas.remove(schema)

    if not schemas:
        exit_with_error(f"No storage types are available. ")

    schemas = sorted(schemas, key=lambda s: s.block_type.name)

    app.console.print("Found the following storage types:")

    for i, schema in enumerate(schemas):
        app.console.print(f"{i}) {schema.block_type.name}")
        if (
            schema.fields.get("description")
            and not schema.fields["description"].isspace()
        ):
            short_description = schema.fields["description"].strip().splitlines()[0]
        else:
            short_description = "<no description>"
        app.console.print(textwrap.indent(short_description, prefix="    "))

    selection = typer.prompt("Select a storage type to create", type=int)
    try:
        schema = schemas[selection]
    except:
        exit_with_error(f"Invalid selection {selection!r}")

    property_specs = schema.fields["properties"]
    app.console.print(
        f"You've selected {schema.block_type.name}. It has {len(property_specs)} option(s). "
    )
    properties = {}
    required_properties = schema.fields.get("required", property_specs.keys())
    for property, property_spec in property_specs.items():
        required = property in required_properties
        optional = " (optional)" if not required else ""

        if property_spec["type"] == "object":
            # TODO: Look into handling arbitrary types better or avoid having arbitrary
            #       types in storage blocks
            continue

        # TODO: Some fields may have a default we can use instead
        not_provided_value = JSON_TO_PY_EMPTY[property_spec["type"]]
        default = not_provided_value if not required else None

        value = typer.prompt(
            f"{property_spec['title'].upper()}{optional}",
            type=JSON_TO_PY_TYPES[property_spec["type"]],
            default=default,
            show_default=default
            is not not_provided_value,  # Do not show our internal indicator
        )

        if value is not not_provided_value:
            properties[property] = value

    name = typer.prompt("Choose a name for this storage configuration")

    block_cls = Block.get_block_class_from_schema(schema)

    app.console.print("Validating configuration...")
    try:
        block = block_cls(**properties)
    except Exception as exc:
        exit_with_error(f"Validation failed! {str(exc)}")

    app.console.print("Registering storage with server...")
    block_document_id = None
    while not block_document_id:
        async with get_client() as client:
            try:
                block_document = await client.create_block_document(
                    block_document=block._to_block_document(
                        name=name,
                        block_schema_id=schema.id,
                        block_type_id=schema.block_type_id,
                    ),
                )
                block_document_id = block_document.id
            except ObjectAlreadyExists:
                app.console.print(f"[red]The name {name!r} is already taken.[/]")
                name = typer.prompt("Choose a new name for this storage configuration")

    app.console.print(
        f"[green]Registered storage {name!r} with identifier '{block_document_id}'.[/]"
    )

    async with get_client() as client:
        if not await client.get_default_storage_block_document():
            set_default = typer.confirm(
                "You do not have a default storage configuration. "
                "Would you like to set this as your default storage?",
                default=True,
            )

            if set_default:
                await client.set_default_storage_block_document(block_document_id)
                exit_with_success(f"Set default storage to {name!r}.")

            else:
                app.console.print(
                    "Default left unchanged. Use `prefect storage set-default "
                    f"{block_document_id}` to set this as the default storage at a later time."
                )


@storage_config_app.command()
async def set_default(storage_block_document_id: UUID):
    """Change the default storage option."""

    async with get_client() as client:
        try:
            await client.set_default_storage_block_document(storage_block_document_id)
        except ObjectNotFound:
            exit_with_error(f"No storage found for id: {storage_block_document_id}!")

    exit_with_success("Updated default storage!")


@storage_config_app.command()
async def reset_default():
    """Reset the default storage option."""
    async with get_client() as client:
        await client.clear_default_storage_block_document()
    exit_with_success("Cleared default storage!")


@storage_config_app.command()
async def ls():
    """View configured storage options."""

    table = Table(title="Configured Storage")
    table.add_column("ID", style="cyan", justify="right", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Storage Type", style="cyan")
    table.add_column("Server Default", width=15)

    async with get_client() as client:
        block_documents = await client.read_block_documents(block_schema_type="STORAGE")
        default_storage_block_document = (
            await client.get_default_storage_block_document()
        )

    for block_document in block_documents:
        is_default_storage_block_document = (
            False
            if default_storage_block_document is None
            else block_document.id == default_storage_block_document.id
        )
        table.add_row(
            str(block_document.id),
            block_document.name,
            block_document.block_schema.block_type.name,
            Emoji("white_check_mark") if is_default_storage_block_document else None,
        )

    if not default_storage_block_document:
        table.caption = (
            "No default storage is set. Temporary local storage will be used."
            "\nSet a default with `prefect storage set-default <id>`"
        )

    app.console.print(table)
