"""
Dev command — native cyclopts implementation.

Internal Prefect development commands.

Note: This module was trimmed to only the commands still relied on by CI
(build-ui, build-image). The remaining dev subcommands (build-docs, ui, api,
start, container) were removed as part of #20607 since they were unused in
practice. See PrefectHQ/prefect#20607 for details.
"""

import os
import platform
import shutil
import subprocess
import sys
from typing import Annotated, Optional

import cyclopts

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

DEV_HELP = """
Internal Prefect development.

Note that some of these commands require extra dependencies (such as npm)
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


@dev_app.command(name="build-ui")
@with_cli_exception_handling
def build_ui(
    no_install: Annotated[
        bool,
        cyclopts.Parameter(
            "--no-install",
            negative="",
            help="Skip installing npm dependencies before building.",
        ),
    ] = False,
    include_v2: Annotated[
        bool,
        cyclopts.Parameter(
            "--include-v2",
            negative="",
            help="Also build the React UI v2 bundle into the Prefect package.",
        ),
    ] = False,
):
    """Installs dependencies and builds UI locally. Requires npm."""
    import prefect as _prefect
    from prefect.utilities.filesystem import tmpchdir

    _exit_with_error_if_not_editable_install()

    def build_ui_bundle(
        *,
        label: str,
        source_dir: str,
        dist_dir: str,
        target_dir: str,
    ) -> None:
        with tmpchdir(_prefect.__development_base_path__ / source_dir):
            if not no_install:
                _cli.console.print(f"Installing {label} npm packages...")
                try:
                    subprocess.check_output(
                        ["npm", "ci"], shell=sys.platform == "win32"
                    )
                except Exception:
                    _cli.console.print(
                        "npm call failed - try running `nvm use` first.", style="red"
                    )
                    raise
            _cli.console.print(f"Building {label} for distribution...")
            env = os.environ.copy()
            subprocess.check_output(
                ["npm", "run", "build"], env=env, shell=sys.platform == "win32"
            )

        with tmpchdir(_prefect.__development_base_path__):
            if os.path.exists(target_dir):
                _cli.console.print(f"Removing existing {label} build files...")
                shutil.rmtree(target_dir)

            _cli.console.print(f"Copying {label} build into src...")
            shutil.copytree(dist_dir, target_dir)

    build_ui_bundle(
        label="UI",
        source_dir="ui",
        dist_dir="ui/dist",
        target_dir=str(_prefect.__ui_static_path__),
    )

    if include_v2:
        build_ui_bundle(
            label="UI v2",
            source_dir="ui-v2",
            dist_dir="ui-v2/dist",
            target_dir=str(_prefect.__ui_v2_static_path__),
        )

    _cli.console.print("Complete!")


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
