"""
Command line interface for working with Orion
"""
import json
import os
import shutil
import subprocess
from functools import partial
from string import Template

import anyio
import typer
import watchgod

import prefect
from prefect.cli.base import app, console
from prefect.cli.orion import open_process_and_stream_output
from prefect.cli.orion import start as start_orion
from prefect.cli.agent import start as start_agent
from prefect.flow_runners import get_prefect_image_name
from prefect.utilities.asyncio import sync_compatible
from prefect.utilities.filesystem import tmpchdir

DEV_HELP = """
Commands for development.

Note that many of these commands require extra dependencies (such as npm and MkDocs) to function properly.
"""
dev_app = typer.Typer(name="dev", short_help="Commands for development.", help=DEV_HELP)
app.add_typer(dev_app)


@dev_app.command()
def build_docs(
    schema_path: str = None,
):
    """
    Builds REST API reference documentation for static display.

    Note that this command only functions properly with an editable install.
    """
    # Delay this import so we don't instantiate the API uncessarily
    from prefect.orion.api.server import app as orion_fastapi_app

    schema = orion_fastapi_app.openapi()

    if not schema_path:
        schema_path = (
            prefect.__root_path__ / "docs" / "api-ref" / "schema.json"
        ).absolute()
    # overwrite info for display purposes
    schema["info"] = {}
    with open(schema_path, "w") as f:
        json.dump(schema, f)
    console.print(f"OpenAPI schema written to {schema_path}")


BUILD_UI_HELP = f"""
Installs dependencies and builds UI locally.

The built UI will be located at {prefect.__root_path__ / "orion-ui"}

Requires npm.
"""


@dev_app.command(help=BUILD_UI_HELP)
def build_ui():
    with tmpchdir(prefect.__root_path__):
        with tmpchdir(prefect.__root_path__ / "orion-ui"):

            console.print("Installing npm packages...")
            subprocess.check_output(["npm", "ci", "install"])

            console.print("Building for distribution...")
            env = os.environ.copy()
            env["ORION_UI_SERVE_BASE"] = "/"
            subprocess.check_output(["npm", "run", "build"], env=env)

        if os.path.exists(prefect.__ui_static_path__):
            console.print("Removing existing build files...")
            shutil.rmtree(prefect.__ui_static_path__)

        console.print("Copying build into src...")
        shutil.copytree("orion-ui/dist", prefect.__ui_static_path__)

    console.print("Complete!")


@dev_app.command()
@sync_compatible
async def ui():
    """
    Starts a hot-reloading dev UI.
    """
    with tmpchdir(prefect.__root_path__):
        with tmpchdir(prefect.__root_path__ / "orion-ui"):
            console.print("Installing npm packages...")
            subprocess.check_output(["npm", "install"])

            console.print("Starting UI development server...")
            await open_process_and_stream_output(command=["npm", "run", "serve"])


@dev_app.command()
@sync_compatible
async def api(
    host: str = prefect.settings.orion.api.host,
    port: int = prefect.settings.orion.api.port,
    log_level: str = "DEBUG",
    services: bool = True,
):
    server_env = os.environ.copy()
    server_env["PREFECT_ORION_SERVICES_RUN_IN_APP"] = str(services)
    server_env["PREFECT_ORION_SERVICES_UI"] = "False"

    await open_process_and_stream_output(
        command=[
            "uvicorn",
            "prefect.orion.api.server:app",
            "--host",
            str(host),
            "--port",
            str(port),
            "--log-level",
            log_level.lower(),
            "--reload",
            "--reload-dir",
            prefect.__module_path__,
        ],
        env=server_env,
    )


@dev_app.command()
@sync_compatible
async def agent(host: str = prefect.settings.orion_host):
    await watchgod.arun_process(
        prefect.__module_path__, start_agent, kwargs=dict(host=host)
    )


@dev_app.command()
@sync_compatible
async def start(
    exclude_api: bool = typer.Option(False, "--no-api"),
    exclude_ui: bool = typer.Option(False, "--no-ui"),
    exclude_agent: bool = typer.Option(False, "--no-agent"),
):
    """
    Starts a hot-reloading development server with API, UI, and agent processes.

    Each service has an individual command if you wish to start them separately.
    Each service can be excluded here as well.
    """
    async with anyio.create_task_group() as tg:
        if not exclude_api:
            tg.start_soon(api)
        if not exclude_ui:
            tg.start_soon(ui)
        if not exclude_agent:
            # Hook the agent to the hosted API if running
            if not exclude_api:
                host = f"http://{prefect.settings.orion.api.host}:{prefect.settings.orion.api.port}/api"
            else:
                host = prefect.settings.orion_host
            tg.start_soon(agent, host)


@dev_app.command()
def kubernetes_manifest():
    """
    Generates a kubernetes manifest for development.

    Example:
        $ prefect dev kubernetes-manifest | kubectl apply -f -
    """

    template = Template(
        (
            prefect.__module_path__ / "cli" / "templates" / "kubernetes-dev.yaml"
        ).read_text()
    )
    manifest = template.substitute(
        {
            "prefect_root_directory": prefect.__root_path__,
            "image_name": get_prefect_image_name(),
        }
    )
    print(manifest)
