import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from typing_extensions import Annotated

from prefect._internal.concurrency.api import create_call, from_async
from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.runner.runner import Runner
from prefect.settings import PREFECT_UI_URL
from prefect.utilities.dockerutils import (
    build_image,
    get_prefect_image_name,
)
from prefect.utilities.importtools import import_object

runner_cli_app = PrefectTyper(
    name="runner",
    help="Commands for working with runners.",
)

app.add_typer(runner_cli_app)


@runner_cli_app.command()
async def serve(
    entrypoint: Annotated[
        Optional[str],
        typer.Argument(
            ...,
            help=(
                "The entrypoint for the runner. Should be in the format"
                " path/to/runner_file.py:runner_variable_name"
            ),
        ),
    ] = None,
):
    """
    Starts up the specified runner to serve the registered flows.
    """
    if entrypoint is None:
        entrypoint = os.environ.get("PREFECT__RUNNER_ENTRYPOINT")

    if entrypoint is None:
        raise typer.BadParameter(
            "No entrypoint provided. Please provide an entrypoint via the command line"
            " or by setting the PREFECT__RUNNER_ENTRYPOINT environment variable."
        )

    runner: Runner = await from_async.wait_for_call_in_new_thread(
        create_call(import_object, entrypoint)
    )

    help_message_top = (
        "[green]Your deployments are being served and your runner is polling for"
        " scheduled runs!\n[/]"
    )

    table = Table(title="Deployments", show_header=False)

    table.add_column(style="blue", no_wrap=True)

    for deployment in runner.registered_deployments:
        table.add_row(f"{deployment.flow_name}/{deployment.name}")

    help_message_bottom = (
        "\nTo trigger any of these deployments, use the"
        " following command:\n[blue]\n\t$ prefect deployment run"
        " [DEPLOYMENT_NAME]\n[/]"
    )
    if PREFECT_UI_URL:
        help_message_bottom += (
            "\nYou can also trigger your deployments via the Prefect UI:"
            f" [blue]{PREFECT_UI_URL.value()}/deployments[/]\n"
        )

    app.console.print(Panel(Group(help_message_top, table, help_message_bottom)))

    await runner.start()


@runner_cli_app.command()
async def build(
    entrypoint: Annotated[
        str,
        typer.Argument(
            ...,
            help=(
                "The entrypoint for the runner. Should be in the format"
                " path/to/runner_file.py:runner_variable_name"
            ),
        ),
    ],
    tag: Annotated[
        str,
        typer.Option(
            ...,
            "--tag",
            "-t",
            help="Name and optionally a tag in the 'name:tag' format.",
        ),
    ],
    dockerfile: Annotated[
        str,
        typer.Option(
            "--dockerfile",
            "-f",
            help=(
                "Dockerfile to use for building the image. If not provided, a"
                " Dockerfile will be generated."
            ),
        ),
    ] = "auto",
):
    auto_build = dockerfile == "auto"
    if auto_build:
        temp_dockerfile = Path("Dockerfile")
        if Path(temp_dockerfile).exists():
            raise ValueError(
                "Cannot generate a Dockerfile. A Dockerfile already exists in the"
                " current directory."
            )

        lines = []
        base_image = get_prefect_image_name()
        lines.append(f"FROM {base_image}")
        dir_name = Path.cwd().name

        if Path("requirements.txt").exists():
            lines.append(
                f"COPY requirements.txt /opt/prefect/{dir_name}/requirements.txt"
            )
            lines.append(
                f"RUN python -m pip install -r /opt/prefect/{dir_name}/requirements.txt"
            )

        lines.append(f"COPY . /opt/prefect/{dir_name}/")
        lines.append(f"WORKDIR /opt/prefect/{dir_name}/")
        lines.append(f"ENV PREFECT__RUNNER_ENTRYPOINT={entrypoint}")
        lines.append("CMD prefect runner serve")

        with Path(temp_dockerfile).open("w") as f:
            f.writelines(line + "\n" for line in lines)

        build_dockerfile = str(temp_dockerfile)
    else:
        build_dockerfile = dockerfile

    build_image(context=Path.cwd(), dockerfile=build_dockerfile, pull=True, tag=tag)

    app.console.print("Successfully built runner image!")
