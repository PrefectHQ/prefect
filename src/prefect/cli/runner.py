import os
from pathlib import Path
from typing import Optional

import typer
from anyio import run_sync_in_worker_thread
from rich.console import Group
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
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

    if entrypoint is not None:
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
    else:
        raise typer.BadParameter(
            "No entrypoint provided. Please provide an entrypoint via the command line"
            " or by setting the PREFECT__RUNNER_ENTRYPOINT environment variable."
        )


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
    with Progress(
        SpinnerColumn(), TextColumn("Building runner image..."), transient=True
    ) as progress:
        docker_build_task = progress.add_task("docker_build", total=1)
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
                    "RUN python -m pip install -r"
                    f" /opt/prefect/{dir_name}/requirements.txt"
                )

            lines.append(f"COPY . /opt/prefect/{dir_name}/")
            lines.append(f"WORKDIR /opt/prefect/{dir_name}/")
            lines.append(f"ENV PREFECT__RUNNER_ENTRYPOINT={entrypoint}")

            with Path(temp_dockerfile).open("w") as f:
                f.writelines(line + "\n" for line in lines)

            build_dockerfile = str(temp_dockerfile)
        else:
            build_dockerfile = dockerfile

        try:
            build_image(context=Path.cwd(), dockerfile=build_dockerfile, tag=tag)
        finally:
            progress.update(docker_build_task, completed=1)
            if auto_build:
                Path("Dockerfile").unlink()

    app.console.print(f"Successfully built runner image {tag!r}\n", style="green")
    app.console.print(
        "You can deploy the flows registered with your runner to a work pool by pushing"
        " your image to a registry and running:\n"
    )
    app.console.print(
        f"\t$ prefect runner deploy -i {tag} -e {entrypoint} -p WORK_POOL\n",
        style="blue",
    )


@runner_cli_app.command()
async def deploy(
    work_pool_name: Annotated[
        str,
        typer.Option(
            ...,
            "--pool",
            "-p",
            help="The name of the work pool to deploy the runner to.",
        ),
    ],
    entrypoint: Annotated[
        str,
        typer.Option(
            ...,
            "--entrypoint",
            "-e",
            help=(
                "The entrypoint for the runner. Should be in the format"
                " path/to/runner_file.py:runner_variable_name"
            ),
        ),
    ],
    image: Annotated[
        str,
        typer.Option(
            ...,
            "--image",
            "-i",
            help="Image name and optionally a tag in the 'name:tag' format.",
        ),
    ],
):
    runner: Runner = await run_sync_in_worker_thread(import_object, entrypoint)

    for deployment in runner.registered_deployments:
        await deployment.apply(work_pool_name=work_pool_name, image=image)

    help_message_top = (
        f"[green]Your deployments have been registered with the {work_pool_name!r} work"
        " pool!\n[/]"
    )

    table = Table(title="Deployments", show_header=False)

    table.add_column(style="blue", no_wrap=True)

    for deployment in runner.registered_deployments:
        table.add_row(f"{deployment.flow_name}/{deployment.name}")

    worker_help_message = (
        "\nTo start a worker that will manage dynamic infrastructure for these"
        " deployments, use the following command:\n[blue]\n\t$ prefect worker start"
        f" --pool {work_pool_name!r}[/]"
    )

    help_message_bottom = (
        "\nAfter starting a worker, trigger any of these deployments using the"
        " following command:\n[blue]\n\t$ prefect deployment run"
        " [DEPLOYMENT_NAME]\n[/]"
    )
    if PREFECT_UI_URL:
        help_message_bottom += (
            "\nYou can also trigger your deployments via the Prefect UI:"
            f" [blue]{PREFECT_UI_URL.value()}/deployments[/]\n"
        )

    app.console.print(
        Panel(Group(help_message_top, table, worker_help_message, help_message_bottom))
    )
