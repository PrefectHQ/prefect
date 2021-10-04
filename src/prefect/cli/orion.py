"""
Command line interface for working with Orion
"""
import json
import os
import typer
import uvicorn

from prefect.orion.api.server import app as orion_fastapi_app
from prefect.cli.base import app, console, exit_with_error, exit_with_success
from prefect import settings
from prefect.utilities.asyncio import sync_compatible
from prefect.orion.utilities.database import drop_db, create_db, get_engine

orion_app = typer.Typer(name="orion")
app.add_typer(orion_app)


@orion_app.command()
def start(
    host: str = settings.orion.api.host,
    port: int = settings.orion.api.port,
    log_level: str = settings.logging.default_level,
    services: bool = True,
):
    """Start an Orion server"""
    console.print("Starting Orion API...")
    # Toggle `run_in_app` (settings are frozen and so it requires a forced update)
    # See https://github.com/PrefectHQ/orion/issues/281
    object.__setattr__(settings.orion.services, "run_in_app", services)
    uvicorn.run(orion_fastapi_app, host=host, port=port, log_level=log_level.lower())
    console.print("Orion stopped!")


@orion_app.command()
@sync_compatible
async def reset_db(yes: bool = typer.Option(False, "--yes", "-y")):
    """Drop and recreate all Orion database tables"""
    engine = await get_engine()
    if not yes:
        confirm = typer.confirm(
            f'Are you sure you want to reset the Orion database located at "{engine.url}"? This will drop and recreate all tables.'
        )
        if not confirm:
            exit_with_error("Database reset aborted")
    console.print("Resetting Orion database...")
    console.print("Droping tables...")
    await drop_db()
    console.print("Creating tables...")
    await create_db()
    exit_with_success(f'Orion database "{engine.url}" reset!')


@orion_app.command()
def build_docs(schema_path: str = None):
    """
    Builds REST API reference documentation for static display.

    Note that this command only functions properly with an editable install.
    """
    if not schema_path:
        schema_path = os.path.abspath(
            os.path.join(__file__, "../../../../docs/api-ref/schema.json")
        )

    schema = orion_fastapi_app.openapi()

    # overwrite info for display purposes
    schema["info"] = {}
    with open(schema_path, "w") as f:
        json.dump(schema, f)
    console.print(f"OpenAPI schema written to {schema_path}")
