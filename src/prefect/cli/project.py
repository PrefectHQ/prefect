"""
Deprecated - Command line interface for working with projects.
"""
from pathlib import Path
from typing import List
from prefect._internal.compatibility.deprecated import generate_deprecation_message

import typer
import yaml
from rich.table import Table

from prefect.cli._prompts import prompt_select_from_table

import prefect
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app, is_interactive
from prefect.client.orchestration import get_client
from prefect.exceptions import ObjectNotFound
from prefect.deployments import find_prefect_directory, initialize_project
from prefect.deployments import register_flow as register

from prefect.deployments.steps.core import run_steps

# Deprecated compatibility
project_app = PrefectTyper(
    name="project",
    help="Deprecated. Use `prefect init` instead.",
    deprecated=True,
    deprecated_name="prefect project",
    deprecated_start_date="Jun 2023",
    deprecated_help="Use `prefect` instead.",
)
app.add_typer(project_app, aliases=["projects"])

recipe_app = PrefectTyper(
    name="recipe",
    help="Deprecated. Use `prefect init` instead.",
    deprecated=True,
    deprecated_name="prefect project recipe",
    deprecated_start_date="Jun 2023",
    deprecated_help="Use `prefect init` instead.",
)
project_app.add_typer(recipe_app, aliases=["recipes"])


@recipe_app.command()
async def ls():
    """
    List available recipes.
    """

    recipe_paths = prefect.__module_path__ / "deployments" / "recipes"
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
@app.command()
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
    recipe_paths = prefect.__module_path__ / "deployments" / "recipes"

    for field in fields:
        key, value = field.split("=")
        inputs[key] = value

    if not recipe and is_interactive():
        recipe_paths = prefect.__module_path__ / "deployments" / "recipes"
        recipes = []

        for r in recipe_paths.iterdir():
            if r.is_dir() and (r / "prefect.yaml").exists():
                with open(r / "prefect.yaml") as f:
                    recipe_data = yaml.safe_load(f)
                    recipe_name = r.name
                    recipe_description = recipe_data.get(
                        "description", "(no description available)"
                    )
                    recipe_dict = {
                        "name": recipe_name,
                        "description": recipe_description,
                    }
                    recipes.append(recipe_dict)

        selected_recipe = prompt_select_from_table(
            app.console,
            "Would you like to initialize your deployment configuration with a recipe?",
            columns=[
                {"header": "Name", "key": "name"},
                {"header": "Description", "key": "description"},
            ],
            data=recipes,
            opt_out_message="No, I'll use the default deployment configuration.",
            opt_out_response={},
        )
        if selected_recipe != {}:
            recipe = selected_recipe["name"]

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
                f"Unknown recipe {recipe!r} provided - run [yellow]`prefect init"
                "`[/yellow] to see all available recipes."
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
    app.console.print(
        generate_deprecation_message(
            "The `prefect project clone` command",
            start_date="Jun 2023",
        )
    )
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

    if deployment.pull_steps:
        output = await run_steps(deployment.pull_steps)
        app.console.out(output["directory"])
    else:
        exit_with_error("No pull steps found, exiting early.")


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
