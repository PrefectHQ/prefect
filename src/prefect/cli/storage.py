"""
Command line interface for managing storage settings
"""
import json
import textwrap
from typing import Any, Callable, Coroutine, Dict, Tuple

import pendulum
import typer
from rich.pretty import Pretty

from prefect.blocks.core import get_block_class
from prefect.cli.base import (
    PrefectTyper,
    app,
    console,
    exit_with_error,
    exit_with_success,
)
from prefect.client import get_client
from prefect.settings import PREFECT_HOME
from prefect.utilities.asyncio import sync_compatible

storage_config_app = PrefectTyper(
    name="storage",
    help="Commands for managing storage settings",
)
app.add_typer(storage_config_app)

JSON_TO_PY_TYPES = {"string": str}
JSON_TO_PY_EMPTY = {"string": "NOT-PROVIDED"}


@storage_config_app.command()
async def configure():

    # valid_storageblocks = storage_configuration_procedures.keys()
    # if storage_type not in valid_storageblocks:
    #     exit_with_error(
    #         f"Invalid storage type: pick one of {list(valid_storageblocks)}"
    #     )

    async with get_client() as client:
        specs = await client.read_block_specs("STORAGE")

    unconfigurable = set()
    for spec in specs:
        for property, property_spec in spec.fields["properties"].items():
            if (
                property_spec["type"] == "object"
                and property in spec.fields["required"]
            ):
                unconfigurable.add(spec)

    for spec in unconfigurable:
        specs.remove(spec)

    console.print("Found the following storage types:")
    for i, spec in enumerate(specs):
        console.print(f"{i}) {spec.name}")
        description = spec.fields["description"]
        if description:
            console.print(textwrap.indent(description, prefix="    "))

    selection = typer.prompt("Select a storage type to configure", type=int)

    try:
        spec = specs[selection]
    except:
        exit_with_error(f"Invalid selection {selection!r}")

    console.print(f"You've selected {spec.name}. Let's configure it...")

    properties = {}
    required_properties = spec.fields.get("required", spec.fields["properties"].keys())
    for property, property_spec in spec.fields["properties"].items():
        print(spec.fields)
        required = property in required_properties
        optional = " (optional)" if not required else ""

        if property_spec["type"] == "object":
            # TODO: Look into handling arbitrary types better or avoid having arbitrary
            #       types in storage blocks
            continue

        # TODO: Some fields may have a default we can display
        not_provided_value = JSON_TO_PY_EMPTY[property_spec["type"]]
        default = not_provided_value if not required else None

        value = typer.prompt(
            f"{property_spec['title']}{optional}",
            type=JSON_TO_PY_TYPES[property_spec["type"]],
            default=default,
            show_default=default
            is not not_provided_value,  # Do not show our internal indicator
        )

        if value is not not_provided_value:
            properties[property] = value

    name = typer.prompt("Choose a name for this storage configuration")

    block_cls = get_block_class(spec.name, spec.version)

    console.print("Validating configuration...")
    try:
        block = block_cls(**properties)
    except Exception as exc:
        exit_with_error(f"Validation failed! {str(exc)}")

    async with get_client() as client:
        await client.create_block(block=block, block_spec_id=spec.id, name=name)

    #     await client.read_block(
    #         name="ORION-CONFIG-STORAGE",
    #         new_name=f"ORION-CONFIG-STORAGE-ARCHIVED-{pendulum.now('UTC')}",
    #         raise_for_status=False,
    #     )

    #     block_ref, data = await storage_configuration_procedures[storage_type]()

    # async with get_client() as client:
    #     await client.create_block(
    #         block=
    #     )

    #     exit_with_success("Successfully configured Orion storage location!")
