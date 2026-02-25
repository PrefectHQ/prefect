"""
Dev command — native cyclopts implementation.

Internal Prefect development commands.
"""

import os
import platform
import shutil
import subprocess
import sys
import textwrap
import time
from functools import partial
from typing import Annotated, Optional

import cyclopts

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

# Module-level import for test patchability
from prefect.utilities.processutils import run_process  # noqa: E402

DEV_HELP = """
Internal Prefect development.

Note that many of these commands require extra dependencies (such as npm and MkDocs)
to function properly.
"""

dev_app: cyclopts.App = cyclopts.App(
    name="dev",
    help=DEV_HELP,
    version_flags=[],
    help_flags=["--help"],
)


def _exit_with_error_if_not_editable_install() -> None:
    import prefect as _prefect

    if (
        _prefect.__module_path__.parent == "site-packages"
        or not (_prefect.__development_base_path__ / "pyproject.toml").exists()
    ):
        exit_with_error(
            "Development commands require an editable Prefect installation. "
            "Development commands require content outside of the 'prefect' module  "
            "which is not available when installed into your site-packages. "
            f"Detected module path: {_prefect.__module_path__}."
        )


@dev_app.command(name="build-docs")
@with_cli_exception_handling
def build_docs(schema_path: Optional[str] = None):
    """Builds REST API reference documentation for static display."""
    import json

    import prefect as _prefect

    _exit_with_error_if_not_editable_install()

    from prefect.server.api.server import create_app

    schema = create_app(ephemeral=True).openapi()

    if not schema_path:
        path_to_schema = (
            _prefect.__development_base_path__ / "docs" / "api-ref" / "schema.json"
        ).absolute()
    else:
        path_to_schema = os.path.abspath(schema_path)
    schema["info"] = {}
    with open(path_to_schema, "w") as f:
        json.dump(schema, f)
    _cli.console.print(f"OpenAPI schema written to {path_to_schema}")


@dev_app.command(name="build-ui")
@with_cli_exception_handling
def build_ui(no_install: bool = False):
    """Installs dependencies and builds UI locally. Requires npm."""
    import prefect as _prefect
    from prefect.utilities.filesystem import tmpchdir

    _exit_with_error_if_not_editable_install()
    with tmpchdir(_prefect.__development_base_path__ / "ui"):
        if not no_install:
            _cli.console.print("Installing npm packages...")
            try:
                subprocess.check_output(["npm", "ci"], shell=sys.platform == "win32")
            except Exception:
                _cli.console.print(
                    "npm call failed - try running `nvm use` first.", style="red"
                )
                raise
            _cli.console.print("Building for distribution...")
            env = os.environ.copy()
            subprocess.check_output(
                ["npm", "run", "build"], env=env, shell=sys.platform == "win32"
            )

    with tmpchdir(_prefect.__development_base_path__):
        if os.path.exists(_prefect.__ui_static_path__):
            _cli.console.print("Removing existing build files...")
            shutil.rmtree(_prefect.__ui_static_path__)

        _cli.console.print("Copying build into src...")
        shutil.copytree("ui/dist", _prefect.__ui_static_path__)

    _cli.console.print("Complete!")


@dev_app.command(name="ui")
@with_cli_exception_handling
async def ui():
    """Starts a hot-reloading development UI."""
    import prefect as _prefect
    from prefect.utilities.filesystem import tmpchdir

    _exit_with_error_if_not_editable_install()
    with tmpchdir(_prefect.__development_base_path__ / "ui"):
        _cli.console.print("Installing npm packages...")
        await run_process(["npm", "install"], stream_output=True)

        _cli.console.print("Starting UI development server...")
        await run_process(command=["npm", "run", "serve"], stream_output=True)


@dev_app.command(name="api")
@with_cli_exception_handling
async def api(
    *,
    host: Annotated[
        Optional[str],
        cyclopts.Parameter("--host", help="API host address."),
    ] = None,
    port: Annotated[
        Optional[int],
        cyclopts.Parameter("--port", help="API port number."),
    ] = None,
    log_level: Annotated[
        str,
        cyclopts.Parameter("--log-level", help="Log level for the server."),
    ] = "DEBUG",
    services: Annotated[
        bool,
        cyclopts.Parameter("--services/--no-services", help="Run services in app."),
    ] = True,
):
    """Starts a hot-reloading development API."""
    import signal

    import anyio
    import watchfiles

    import prefect as _prefect
    from prefect.settings import (
        PREFECT_SERVER_API_HOST,
        PREFECT_SERVER_API_PORT,
    )

    resolved_host = host if host is not None else PREFECT_SERVER_API_HOST.value()
    resolved_port = port if port is not None else PREFECT_SERVER_API_PORT.value()

    server_env = os.environ.copy()
    server_env["PREFECT_API_SERVICES_RUN_IN_APP"] = str(services)
    server_env["PREFECT_API_SERVICES_UI"] = "False"
    server_env["PREFECT_UI_API_URL"] = f"http://{resolved_host}:{resolved_port}/api"

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "--factory",
        "prefect.server.api.server:create_app",
        "--host",
        str(resolved_host),
        "--port",
        str(resolved_port),
        "--log-level",
        log_level.lower(),
    ]

    _cli.console.print(f"Running: {' '.join(command)}")

    stop_event = anyio.Event()
    start_command = partial(
        run_process, command=command, env=server_env, stream_output=True
    )

    async with anyio.create_task_group() as tg:
        try:
            server_pid = await tg.start(start_command)
            async for _ in watchfiles.awatch(
                _prefect.__module_path__,
                stop_event=stop_event,  # type: ignore
            ):
                _cli.console.print("Restarting Prefect Server...")
                os.kill(server_pid, signal.SIGTERM)  # type: ignore
                server_pid = await tg.start(start_command)
        except RuntimeError as err:
            if str(err).strip() != "Already borrowed":
                raise
        except KeyboardInterrupt:
            try:
                os.kill(server_pid, signal.SIGTERM)  # type: ignore
            except ProcessLookupError:
                pass
            stop_event.set()


@dev_app.command(name="start")
@with_cli_exception_handling
async def start(
    *,
    exclude_api: Annotated[
        bool,
        cyclopts.Parameter("--no-api", negative="", help="Exclude the API service."),
    ] = False,
    exclude_ui: Annotated[
        bool,
        cyclopts.Parameter("--no-ui", negative="", help="Exclude the UI service."),
    ] = False,
):
    """Starts a hot-reloading development server with API, UI, and agent processes."""
    import anyio

    from prefect.settings import (
        PREFECT_SERVER_API_HOST,
        PREFECT_SERVER_API_PORT,
    )

    async with anyio.create_task_group() as tg:
        if not exclude_api:
            tg.start_soon(
                partial(
                    api,
                    host=PREFECT_SERVER_API_HOST.value(),
                    port=PREFECT_SERVER_API_PORT.value(),
                )
            )
        if not exclude_ui:
            tg.start_soon(ui)


@dev_app.command(name="build-image")
@with_cli_exception_handling
def build_image(
    *,
    arch: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--arch",
            help=(
                "The architecture to build the container for. "
                "Defaults to the architecture of the host Python. "
                f"[default: {platform.machine()}]"
            ),
        ),
    ] = None,
    python_version: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--python-version",
            help=(
                "The Python version to build the container for. "
                "Defaults to the version of the host Python."
            ),
        ),
    ] = None,
    flavor: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--flavor",
            help=(
                "An alternative flavor to build, for example 'conda'. "
                "Defaults to the standard Python base image"
            ),
        ),
    ] = None,
    build_arg: Annotated[
        list[str],
        cyclopts.Parameter(
            "--build-arg",
            help=(
                "This will directly pass a --build-arg into the docker build process. "
                "Can be added to the command line multiple times."
            ),
        ),
    ] = [],
    dry_run: Annotated[
        bool,
        cyclopts.Parameter("--dry-run", help="Print the command instead of running."),
    ] = False,
):
    """Build a docker image for development."""
    import prefect as _prefect
    from prefect.utilities.dockerutils import (
        get_prefect_image_name,
        python_version_minor,
    )

    _exit_with_error_if_not_editable_install()

    arch = arch or platform.machine()
    python_version = python_version or python_version_minor()

    tag = get_prefect_image_name(python_version=python_version, flavor=flavor)

    command = [
        "docker",
        "build",
        str(_prefect.__development_base_path__),
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

    for arg in build_arg:
        command += ["--build-arg", arg]

    if dry_run:
        print(" ".join(command))
        return

    try:
        subprocess.check_call(command, shell=sys.platform == "win32")
    except subprocess.CalledProcessError:
        exit_with_error("Failed to build image!")
    else:
        exit_with_success(f"Built image {tag!r} for linux/{arch}")


@dev_app.command(name="container")
@with_cli_exception_handling
def container(
    *,
    bg: Annotated[
        bool,
        cyclopts.Parameter("--bg", help="Run in background."),
    ] = False,
    name: Annotated[
        str,
        cyclopts.Parameter("--name", help="Container name."),
    ] = "prefect-dev",
    api: Annotated[
        bool,
        cyclopts.Parameter("--api/--no-api", help="Start API in container."),
    ] = True,
    tag: Annotated[
        Optional[str],
        cyclopts.Parameter("--tag", help="Docker image tag."),
    ] = None,
):
    """Run a docker container with local code mounted and installed."""
    import docker
    from docker.models.containers import Container

    import prefect as _prefect
    from prefect.utilities.dockerutils import get_prefect_image_name

    _exit_with_error_if_not_editable_install()

    client = docker.from_env()

    containers = client.containers.list()
    container_names = {c.name for c in containers}
    if name in container_names:
        exit_with_error(
            f"Container {name!r} already exists. Specify a different name or stop "
            "the existing container."
        )

    blocking_cmd = "prefect dev api" if api else "sleep infinity"
    tag = tag or get_prefect_image_name()

    ctr: Container = client.containers.create(
        image=tag,
        command=[
            "/bin/bash",
            "-c",
            (
                "pip install -e /opt/prefect/repo\\[dev\\] && touch /READY &&"
                f" {blocking_cmd}"
            ),
        ],
        name=name,
        auto_remove=True,
        working_dir="/opt/prefect/repo",
        volumes=[f"{_prefect.__development_base_path__}:/opt/prefect/repo"],
        shm_size="4G",
    )

    print(f"Starting container for image {tag!r}...")
    ctr.start()

    print("Waiting for installation to complete", end="", flush=True)
    try:
        ready = False
        while not ready:
            print(".", end="", flush=True)
            result = ctr.exec_run("test -f /READY")
            ready = result.exit_code == 0
            if not ready:
                time.sleep(3)
    except BaseException:
        print("\nInterrupted. Stopping container...")
        ctr.stop()
        raise

    print(
        textwrap.dedent(
            f"""
            Container {ctr.name!r} is ready! To connect to the container, run:

                docker exec -it {ctr.name} /bin/bash
            """
        )
    )

    if bg:
        print(
            textwrap.dedent(
                f"""
                The container will run forever. Stop the container with:

                    docker stop {ctr.name}
                """
            )
        )
        return

    try:
        print("Send a keyboard interrupt to exit...")
        ctr.wait()
    except KeyboardInterrupt:
        pass
    finally:
        print("\nStopping container...")
        ctr.stop()
