"""
Command line interface for working with projects.
"""
from pathlib import Path
from typing import List

import typer
import yaml
from rich.table import Table

import prefect
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

recipe_app = PrefectTyper(
    name="recipe", help="Commands for interacting with project recipes."
)
project_app.add_typer(recipe_app, aliases=["recipes"])


@recipe_app.command()
async def ls():
    """
    List available recipes.
    """

    recipe_paths = prefect.__module_path__ / "projects" / "recipes"
    recipes = {}

    for recipe in recipe_paths.iterdir():
        if recipe.is_dir() and (recipe / "prefect.yaml").exists():
            with open(recipe / "prefect.yaml") as f:
                recipes[recipe.name] = yaml.safe_load(f).get(
                    "description", "(no description available)"
                )

    table = Table(
        title="Available project recipes",
        caption=(
            "Run `prefect project init --recipe <recipe>` to initialize a project with"
            " a recipe."
        ),
        caption_style="red",
    )
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("Description", justify="left", style="white", no_wrap=False)
    for name, description in sorted(recipes.items(), key=lambda x: x[0]):
        table.add_row(name, description)

    app.console.print(table)


@project_app.command()
async def init(
    name: str = None,
    recipe: str = None,
    fields: List[str] = typer.Option(
        None,
        "-f",
        "--field",
        help=(
            "One or more fields to pass to the recipe (e.g., image_name) in the format"
            " of key=value."
        ),
    ),
):
    """
    Initialize a new project.
    """
    inputs = {}
    fields = fields or []
    recipe_paths = prefect.__module_path__ / "projects" / "recipes"

    for field in fields:
        key, value = field.split("=")
        inputs[key] = value

    if recipe and (recipe_paths / recipe / "prefect.yaml").exists():
        with open(recipe_paths / recipe / "prefect.yaml") as f:
            recipe_inputs = yaml.safe_load(f).get("required_inputs") or {}

        if recipe_inputs:
            if set(recipe_inputs.keys()) < set(inputs.keys()):
                # message to user about extra fields
                app.console.print(
                    (
                        f"Warning: extra fields provided for {recipe!r} recipe:"
                        f" '{', '.join(set(inputs.keys()) - set(recipe_inputs.keys()))}'"
                    ),
                    style="red",
                )
            elif set(recipe_inputs.keys()) > set(inputs.keys()):
                table = Table(
                    title=f"[red]Required inputs for {recipe!r} recipe[/red]",
                )
                table.add_column("Field Name", style="green", no_wrap=True)
                table.add_column(
                    "Description", justify="left", style="white", no_wrap=False
                )
                for field, description in recipe_inputs.items():
                    if field not in inputs:
                        table.add_row(field, description)

                app.console.print(table)

                for key, description in recipe_inputs.items():
                    if key not in inputs:
                        inputs[key] = typer.prompt(key)

            app.console.print("-" * 15)

    try:
        files = [
            f"[green]{fname}[/green]"
            for fname in initialize_project(name=name, recipe=recipe, inputs=inputs)
        ]
    except ValueError as exc:
        if "Unknown recipe" in str(exc):
            exit_with_error(
                f"Unknown recipe {recipe!r} provided - run [yellow]`prefect project"
                " recipe ls`[/yellow] to see all available recipes."
            )
        else:
            raise

    files = "\n".join(files)
    empty_msg = (
        f"Created project in [green]{Path('.').resolve()}[/green]; no new files"
        " created."
    )
    file_msg = (
        f"Created project in [green]{Path('.').resolve()}[/green] with the following"
        f" new files:\n{files}"
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
        output = await run_step(step)

    app.console.out(output["directory"])


@project_app.command()
async def register_flow(
    entrypoint: str = typer.Argument(
        ...,
        help=(
            "The path to a flow entrypoint, in the form of"
            " `./path/to/file.py:flow_func_name`"
        ),
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help=(
            "An optional flag to force register this flow and overwrite any existing"
            " entry"
        ),
    ),
):
    """
    Register a flow with this project.
    """
    try:
        flow = await register(entrypoint, force=force)
    except Exception as exc:
        exit_with_error(exc)

    app.console.print(
        (
            f"Registered flow {flow.name!r} in"
            f" {(find_prefect_directory()/'flows.json').resolve()!s}"
        ),
        style="green",
    )
