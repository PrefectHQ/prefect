"""
Command line interface for working with Orion
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import textwrap
import time
from functools import partial
from string import Template

import anyio
import typer

import prefect
from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.agent import start as start_agent
from prefect.cli.root import app
from prefect.flow_runners.base import get_prefect_image_name, python_version_minor
from prefect.orion.api.server import create_app
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_ORION_API_HOST,
    PREFECT_ORION_API_PORT,
)
from prefect.utilities.filesystem import tmpchdir
from prefect.utilities.processutils import run_process

DEV_HELP = """
Commands for development.

Note that many of these commands require extra dependencies (such as npm and MkDocs) to function properly.
"""
dev_app = PrefectTyper(
    name="dev", short_help="Commands for development.", help=DEV_HELP
)
app.add_typer(dev_app)


def exit_with_error_if_not_editable_install():
    if (
        prefect.__module_path__.parent == "site-packages"
        or not (prefect.__root_path__ / "setup.py").exists()
    ):
        exit_with_error(
            "Development commands cannot be used without an editable installation of Prefect. "
            "Development commands require content outside of the 'prefect' module which "
            "is not available when installed into your site-packages. "
            f"Detected module path: {prefect.__module_path__}."
        )


@dev_app.command()
def build_docs(
    schema_path: str = None,
):
    """
    Builds REST API reference documentation for static display.
    """
    exit_with_error_if_not_editable_install()
    schema = create_app(ephemeral=True).openapi()

    if not schema_path:
        schema_path = (
            prefect.__root_path__ / "docs" / "api-ref" / "schema.json"
        ).absolute()
    # overwrite info for display purposes
    schema["info"] = {}
    with open(schema_path, "w") as f:
        json.dump(schema, f)
    app.console.print(f"OpenAPI schema written to {schema_path}")


BUILD_UI_HELP = f"""
Installs dependencies and builds UI locally.

The built UI will be located at {prefect.__root_path__ / "orion-ui"}

Requires npm.
"""


@dev_app.command(help=BUILD_UI_HELP)
def build_ui():
    exit_with_error_if_not_editable_install()
    with tmpchdir(prefect.__root_path__):
        with tmpchdir(prefect.__root_path__ / "orion-ui"):

            app.console.print("Installing npm packages...")
            try:
                subprocess.check_output(
                    ["npm", "ci", "install"], shell=sys.platform == "win32"
                )
            except Exception as exc:
                app.console.print(
                    "npm call failed - try running `nvm use` first.", style="red"
                )
                raise

            app.console.print("Building for distribution...")
            env = os.environ.copy()
            env["ORION_UI_SERVE_BASE"] = "/"
            subprocess.check_output(
                ["npm", "run", "build"], env=env, shell=sys.platform == "win32"
            )

        if os.path.exists(prefect.__ui_static_path__):
            app.console.print("Removing existing build files...")
            shutil.rmtree(prefect.__ui_static_path__)

        app.console.print("Copying build into src...")
        shutil.copytree("orion-ui/dist", prefect.__ui_static_path__)

    app.console.print("Complete!")


@dev_app.command()
async def ui():
    """
    Starts a hot-reloading development UI.
    """
    exit_with_error_if_not_editable_install()
    with tmpchdir(prefect.__root_path__):
        with tmpchdir(prefect.__root_path__ / "orion-ui"):
            app.console.print("Installing npm packages...")
            subprocess.check_output(["npm", "install"], shell=sys.platform == "win32")

            app.console.print("Starting UI development server...")
            await run_process(command=["npm", "run", "serve"], stream_output=True)


@dev_app.command()
async def api(
    host: str = SettingsOption(PREFECT_ORION_API_HOST),
    port: int = SettingsOption(PREFECT_ORION_API_PORT),
    log_level: str = "DEBUG",
    services: bool = True,
):
    """
    Starts a hot-reloading development API.
    """
    server_env = os.environ.copy()
    server_env["PREFECT_ORION_SERVICES_RUN_IN_APP"] = str(services)
    server_env["PREFECT_ORION_SERVICES_UI"] = "False"

    command = [
        "uvicorn",
        "--factory",
        "prefect.orion.api.server:create_app",
        "--host",
        str(host),
        "--port",
        str(port),
        "--log-level",
        log_level.lower(),
        "--reload",
        "--reload-dir",
        str(prefect.__module_path__),
    ]

    app.console.print(f"Running: {' '.join(command)}")

    await run_process(command=command, env=server_env, stream_output=True)


@dev_app.command()
async def agent(api_url: str = SettingsOption(PREFECT_API_URL)):
    """
    Starts a hot-reloading development agent process.
    """
    # Delayed import since this is only a 'dev' dependency
    import watchfiles

    app.console.print("Creating hot-reloading agent process...")
    await watchfiles.arun_process(
        prefect.__module_path__,
        target=start_agent,
        kwargs=dict(hide_welcome=False, api=api_url),
    )


@dev_app.command()
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
            tg.start_soon(
                partial(
                    api,
                    host=PREFECT_ORION_API_HOST.value(),
                    port=PREFECT_ORION_API_PORT.value(),
                )
            )
        if not exclude_ui:
            tg.start_soon(ui)
        if not exclude_agent:
            # Hook the agent to the hosted API if running
            if not exclude_api:
                host = f"http://{PREFECT_ORION_API_HOST.value()}:{PREFECT_ORION_API_PORT.value()}/api"
            else:
                host = PREFECT_API_URL.value()
            tg.start_soon(agent, host)


@dev_app.command()
def build_image(
    arch: str = typer.Option(
        None,
        help=(
            "The architecture to build the container for. "
            "Defaults to the architecture of the host Python. "
            f"[default: {platform.machine()}]"
        ),
    ),
    python_version: str = typer.Option(
        None,
        help=(
            "The Python version to build the container for. "
            "Defaults to the version of the host Python. "
            f"[default: {python_version_minor()}]"
        ),
    ),
    flavor: str = typer.Option(
        None,
        help=(
            "An alternative flavor to build, for example 'conda'. "
            "Defaults to the standard Python base image"
        ),
    ),
    dry_run: bool = False,
):
    """
    Build a docker image for development.
    """
    exit_with_error_if_not_editable_install()
    # TODO: Once https://github.com/tiangolo/typer/issues/354 is addresesd, the
    #       default can be set in the function signature
    arch = arch or platform.machine()
    python_version = python_version or python_version_minor()

    tag = get_prefect_image_name(python_version=python_version, flavor=flavor)

    # Here we use a subprocess instead of the docker-py client to easily stream output
    # as it comes
    command = [
        "docker",
        "build",
        str(prefect.__root_path__),
        "--tag",
        tag,
        "--platform",
        f"linux/{arch}",
        "--build-arg",
        "PREFECT_EXTRAS=[dev]",
        "--build-arg",
        f"PYTHON_VERSION={python_version}",
    ]

    if flavor:
        command += ["--build-arg", f"BASE_IMAGE=prefect-{flavor}"]

    if dry_run:
        print(" ".join(command))
        return

    try:
        subprocess.check_call(command, shell=sys.platform == "win32")
    except subprocess.CalledProcessError:
        exit_with_error("Failed to build image!")
    else:
        exit_with_success(f"Built image {tag!r} for linux/{arch}")


@dev_app.command()
def container(bg: bool = False, name="prefect-dev", api: bool = True):
    """
    Run a docker container with local code mounted and installed.
    """
    exit_with_error_if_not_editable_install()
    import docker
    from docker.models.containers import Container

    client = docker.from_env()

    containers = client.containers.list()
    container_names = {container.name for container in containers}
    if name in container_names:
        exit_with_error(
            f"Container {name!r} already exists. Specify a different name or stop "
            "the existing container."
        )

    blocking_cmd = "prefect dev api" if api else "sleep infinity"
    tag = get_prefect_image_name()

    container: Container = client.containers.create(
        image=tag,
        command=[
            "/bin/bash",
            "-c",
            f"pip install -e /opt/prefect/repo\\[dev\\] && touch /READY && {blocking_cmd}",
        ],
        name=name,
        auto_remove=True,
        working_dir="/opt/prefect/repo",
        volumes=[f"{prefect.__root_path__}:/opt/prefect/repo"],
        shm_size="4G",
    )

    print(f"Starting container for image {tag!r}...")
    container.start()

    print("Waiting for installation to complete", end="", flush=True)
    try:
        ready = False
        while not ready:
            print(".", end="", flush=True)
            result = container.exec_run("test -f /READY")
            ready = result.exit_code == 0
            if not ready:
                time.sleep(3)
    except:
        print("\nInterrupted. Stopping container...")
        container.stop()
        raise

    print(
        textwrap.dedent(
            f"""
            Container {container.name!r} is ready! To connect to the container, run:

                docker exec -it {container.name} /bin/bash
            """
        )
    )

    if bg:
        print(
            textwrap.dedent(
                f"""
                The container will run forever. Stop the container with:

                    docker stop {container.name}
                """
            )
        )
        # Exit without stopping
        return

    try:
        print("Send a keyboard interrupt to exit...")
        container.wait()
    except KeyboardInterrupt:
        pass  # Avoid showing "Abort"
    finally:
        print("\nStopping container...")
        container.stop()


@dev_app.command()
def kubernetes_manifest():
    """
    Generates a Kubernetes manifest for development.

    Example:
        $ prefect dev kubernetes-manifest | kubectl apply -f -
    """
    exit_with_error_if_not_editable_install()

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
