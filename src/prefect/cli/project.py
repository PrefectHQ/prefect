"""
Command line interface for working with projects.
"""
import json
from pathlib import Path

import typer

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.client.orchestration import get_client
from prefect.exceptions import ObjectNotFound
from prefect.flows import load_flow_from_entrypoint
from prefect.projects import find_prefect_directory, initialize_project
from prefect.projects.steps import run_step
from prefect.utilities.asyncutils import run_sync_in_worker_thread

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
        fpath, obj_name = entrypoint.rsplit(":", 1)
    except ValueError as exc:
        if str(exc) == "not enough values to unpack (expected 2, got 1)":
            missing_flow_name_msg = (
                "Your flow entrypoint must include the name of the function that is"
                f" the entrypoint to your flow.\nTry {entrypoint}:<flow_name>"
            )
            exit_with_error(missing_flow_name_msg)
        else:
            raise exc
    try:
        flow = await run_sync_in_worker_thread(load_flow_from_entrypoint, entrypoint)
    except Exception as exc:
        exit_with_error(exc)

    fpath = Path(fpath).absolute()
    prefect_dir = find_prefect_directory()
    if not prefect_dir:
        exit_with_error(
            "No .prefect directory could be found - run [yellow]`prefect project"
            " init`[/yellow] to create one."
        )

    entrypoint = f"{fpath.relative_to(prefect_dir.parent)!s}:{obj_name}"

    if (prefect_dir / "flows.json").exists():
        with open(prefect_dir / "flows.json", "r") as f:
            flows = json.load(f)
    else:
        flows = {}

    flows[flow.name] = entrypoint

    with open(prefect_dir / "flows.json", "w") as f:
        json.dump(flows, f, sort_keys=True, indent=2)

    app.console.print(
        f"Registered flow {flow.name!r} in {(prefect_dir/'flows.json').resolve()!s}",
        style="green",
    )
