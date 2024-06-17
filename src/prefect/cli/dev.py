"""
Command line interface for working with Prefect Server
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
from typing import Optional

import anyio
import typer

import prefect
from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.settings import (
    PREFECT_SERVER_API_HOST,
    PREFECT_SERVER_API_PORT,
)
from prefect.utilities.dockerutils import get_prefect_image_name, python_version_minor
from prefect.utilities.filesystem import tmpchdir
from prefect.utilities.processutils import run_process

DEV_HELP = """
Internal Prefect development.

Note that many of these commands require extra dependencies (such as npm and MkDocs)
to function properly.
"""
dev_app = PrefectTyper(
    name="dev", short_help="Internal Prefect development.", help=DEV_HELP
)
app.add_typer(dev_app)


def exit_with_error_if_not_editable_install():
    if (
        prefect.__module_path__.parent == "site-packages"
        or not (prefect.__development_base_path__ / "setup.py").exists()
    ):
        exit_with_error(
            "Development commands require an editable Prefect installation. "
            "Development commands require content outside of the 'prefect' module  "
            "which is not available when installed into your site-packages. "
            f"Detected module path: {prefect.__module_path__}."
        )


@dev_app.command()
def build_docs(schema_path: Optional[str] = None):
    """
    Builds REST API reference documentation for static display.
    """
    exit_with_error_if_not_editable_install()

    from prefect.server.api.server import create_app

    schema = create_app(ephemeral=True).openapi()

    if not schema_path:
        path_to_schema = (
            prefect.__development_base_path__ / "docs" / "api-ref" / "schema.json"
        ).absolute()
    else:
        path_to_schema = os.path.abspath(schema_path)
    # overwrite info for display purposes
    schema["info"] = {}
    with open(path_to_schema, "w") as f:
        json.dump(schema, f)
    app.console.print(f"OpenAPI schema written to {path_to_schema}")


BUILD_UI_HELP = f"""
Installs dependencies and builds UI locally.

The built UI will be located at {prefect.__development_base_path__ / "ui"}

Requires npm.
"""


@dev_app.command(help=BUILD_UI_HELP)
def build_ui(
    no_install: bool = False,
):
    exit_with_error_if_not_editable_install()
    with tmpchdir(prefect.__development_base_path__ / "ui"):
        if not no_install:
            app.console.print("Installing npm packages...")
            try:
                subprocess.check_output(["npm", "ci"], shell=sys.platform == "win32")
            except Exception:
                app.console.print(
                    "npm call failed - try running `nvm use` first.", style="red"
                )
                raise
            app.console.print("Building for distribution...")
            env = os.environ.copy()
            subprocess.check_output(
                ["npm", "run", "build"], env=env, shell=sys.platform == "win32"
            )

    with tmpchdir(prefect.__development_base_path__):
        if os.path.exists(prefect.__ui_static_path__):
            app.console.print("Removing existing build files...")
            shutil.rmtree(prefect.__ui_static_path__)

        app.console.print("Copying build into src...")
        shutil.copytree("ui/dist", prefect.__ui_static_path__)

    app.console.print("Complete!")


@dev_app.command()
async def ui():
    """
    Starts a hot-reloading development UI.
    """
    exit_with_error_if_not_editable_install()
    with tmpchdir(prefect.__development_base_path__ / "ui"):
        app.console.print("Installing npm packages...")
        await run_process(["npm", "install"], stream_output=True)

        app.console.print("Starting UI development server...")
        await run_process(command=["npm", "run", "serve"], stream_output=True)


@dev_app.command()
async def api(
    host: str = SettingsOption(PREFECT_SERVER_API_HOST),
    port: int = SettingsOption(PREFECT_SERVER_API_PORT),
    log_level: str = "DEBUG",
    services: bool = True,
):
    """
    Starts a hot-reloading development API.
    """
    import watchfiles

    server_env = os.environ.copy()
    server_env["PREFECT_API_SERVICES_RUN_IN_APP"] = str(services)
    server_env["PREFECT_API_SERVICES_UI"] = "False"
    server_env["PREFECT_UI_API_URL"] = f"http://{host}:{port}/api"

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "--factory",
        "prefect.server.api.server:create_app",
        "--host",
        str(host),
        "--port",
        str(port),
        "--log-level",
        log_level.lower(),
    ]

    app.console.print(f"Running: {' '.join(command)}")
    import signal

    stop_event = anyio.Event()
    start_command = partial(
        run_process, command=command, env=server_env, stream_output=True
    )

    async with anyio.create_task_group() as tg:
        try:
            server_pid = await tg.start(start_command)
            async for _ in watchfiles.awatch(
                prefect.__module_path__,
                stop_event=stop_event,  # type: ignore
            ):
                # when any watched files change, restart the server
                app.console.print("Restarting Prefect Server...")
                os.kill(server_pid, signal.SIGTERM)  # type: ignore
                # start a new server
                server_pid = await tg.start(start_command)
        except RuntimeError as err:
            # a bug in watchfiles causes an 'Already borrowed' error from Rust when
            # exiting: https://github.com/samuelcolvin/watchfiles/issues/200
            if str(err).strip() != "Already borrowed":
                raise
        except KeyboardInterrupt:
            # exit cleanly on ctrl-c by killing the server process if it's
            # still running
            try:
                os.kill(server_pid, signal.SIGTERM)  # type: ignore
            except ProcessLookupError:
                # process already exited
                pass

            stop_event.set()


@dev_app.command()
async def start(
    exclude_api: bool = typer.Option(False, "--no-api"),
    exclude_ui: bool = typer.Option(False, "--no-ui"),
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
                    # CLI commands are wrapped in sync_compatible, but this
                    # task group is async, so we need use the wrapped function
                    # directly
                    api.aio,
                    host=PREFECT_SERVER_API_HOST.value(),
                    port=PREFECT_SERVER_API_PORT.value(),
                )
            )
        if not exclude_ui:
            tg.start_soon(ui.aio)


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
    # TODO: Once https://github.com/tiangolo/typer/issues/354 is addressed, the
    #       default can be set in the function signature
    arch = arch or platform.machine()
    python_version = python_version or python_version_minor()

    tag = get_prefect_image_name(python_version=python_version, flavor=flavor)

    # Here we use a subprocess instead of the docker-py client to easily stream output
    # as it comes
    command = [
        "docker",
        "build",
        str(prefect.__development_base_path__),
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
def container(
    bg: bool = False, name="prefect-dev", api: bool = True, tag: Optional[str] = None
):
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
    tag = tag or get_prefect_image_name()

    container: Container = client.containers.create(
        image=tag,
        command=[
            "/bin/bash",
            "-c",
            (  # noqa
                "pip install -e /opt/prefect/repo\\[dev\\] && touch /READY &&"
                f" {blocking_cmd}"
            ),
        ],
        name=name,
        auto_remove=True,
        working_dir="/opt/prefect/repo",
        volumes=[f"{prefect.__development_base_path__}:/opt/prefect/repo"],
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
    except BaseException:
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
            "prefect_root_directory": prefect.__development_base_path__,
            "image_name": get_prefect_image_name(),
        }
    )
    print(manifest)
