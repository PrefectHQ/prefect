"""
Command line interface for working with projects.
"""
from pathlib import Path

import typer

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.client.orchestration import get_client
from prefect.exceptions import ObjectNotFound
from prefect.projects import find_prefect_directory, initialize_project
from prefect.projects import register_flow as register
from prefect.projects.steps import run_step

project_app = PrefectTyper(
    name="project", help="Commands for interacting with your Prefect project."
)
app.add_typer(project_app, aliases=["projects"])


@project_app.command()
async def init(name: str = None):
    """
    Initialize a new project.
    """

    files = [f"[green]{fname}[/green]" for fname in initialize_project(name=name)]

    files = "\n".join(files)
    empty_msg = (
        f"Created project in [green]{Path('.').resolve()}[/green]; no new files"
        " created."
    )
    file_msg = (
        f"Created project in [green]{Path('.').resolve()}[/green] with the following"
        f" new files:\n {files}"
    )
    app.console.print(file_msg if files else empty_msg)


@project_app.command()
async def clone(
    deployment_name: str = typer.Option(
        None,
        "--deployment",
        "-d",
        help="The name of the deployment to clone a project for.",
    ),
    deployment_id: str = typer.Option(
        None,
        "--id",
        "-i",
        help="The id of the deployment to clone a project for.",
    ),
):
    """
    Clone an existing project for a given deployment.
    """
    if deployment_name and deployment_id:
        exit_with_error(
            "Can only pass one of deployment name or deployment ID options."
        )

    if not deployment_name and not deployment_id:
        exit_with_error("Must pass either a deployment name or deployment ID.")

    if deployment_name:
        async with get_client() as client:
            try:
                deployment = await client.read_deployment_by_name(deployment_name)
            except ObjectNotFound:
                exit_with_error(f"Deployment {deployment_name!r} not found!")
    else:
        async with get_client() as client:
            try:
                deployment = await client.read_deployment(deployment_id)
            except ObjectNotFound:
                exit_with_error(f"Deployment {deployment_id!r} not found!")

    if not deployment.pull_steps:
        exit_with_error("No pull steps found, exiting early.")

    # TODO: allow for passing values between steps / stacking them
    for step in deployment.pull_steps:
        output = run_step(step)

    app.console.out(output["directory"])


@project_app.command()
async def register_flow(
    entrypoint: str = typer.Argument(
        ...,
        help=(
            "The path to a flow entrypoint, in the form of"
            " `./path/to/file.py:flow_func_name`"
        ),
    )
):
    """
    Register a flow with this project.
    """
    try:
        flow = await register(entrypoint)
    except Exception as exc:
        exit_with_error(exc)

    app.console.print(
        (
            f"Registered flow {flow.name!r} in"
            f" {(find_prefect_directory()/'flows.json').resolve()!s}"
        ),
        style="green",
    )
