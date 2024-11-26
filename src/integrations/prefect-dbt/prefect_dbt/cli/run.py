"""
CLI interface for dbt run commands
"""
from typing import List, Optional

import typer

from prefect import Flow
from prefect.cli._utilities import with_cli_exception_handling
from prefect_dbt.cli.root import app
from prefect_dbt.core.commands import trigger_dbt_cli_command


@app.command()
@with_cli_exception_handling
def run(
    ctx: typer.Context,
    models: Optional[List[str]] = typer.Option(
        None,
        "--models",
        "-m",
        help="Specify the models to include.",
    ),
    exclude: Optional[List[str]] = typer.Option(
        None,
        "--exclude",
        "-e",
        help="Specify models to exclude.",
    ),
    select: Optional[List[str]] = typer.Option(
        None,
        "--select",
        "-s",
        help="Specify models to select.",
    ),
    selector: Optional[str] = typer.Option(
        None,
        "--selector",
        help="Specify selector name from dbt_project.yml",
    ),
    vars: Optional[str] = typer.Option(
        None,
        "--vars",
        help="Supply variables to the project.",
    ),
    project_dir: str = typer.Option(
        ".",
        "--project-dir",
        help="The directory containing your dbt project.",
    ),
    profiles_dir: Optional[str] = typer.Option(
        None,
        "--profiles-dir",
        help="The directory containing your profiles.yml file.",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="The profile to use from profiles.yml.",
    ),
    target: Optional[str] = typer.Option(
        None,
        "--target",
        "-t",
        help="The target to use from profiles.yml.",
    ),
    threads: Optional[int] = typer.Option(
        None,
        "--threads",
        help="Specify number of threads to use.",
    ),
    full_refresh: bool = typer.Option(
        False,
        "--full-refresh",
        help="Perform full refresh of incremental models.",
    ),
):
    """
    Run dbt models for your project.
    """
    # Build command arguments
    extra_command_args = []

    if models:
        extra_command_args.extend(["--models", " ".join(models)])
    if exclude:
        extra_command_args.extend(["--exclude", " ".join(exclude)])
    if select:
        extra_command_args.extend(["--select", " ".join(select)])
    if selector:
        extra_command_args.extend(["--selector", selector])
    if vars:
        extra_command_args.extend(["--vars", vars])
    if profiles_dir:
        extra_command_args.extend(["--profiles-dir", profiles_dir])
    if profile:
        extra_command_args.extend(["--profile", profile])
    if target:
        extra_command_args.extend(["--target", target])
    if threads:
        extra_command_args.extend(["--threads", str(threads)])
    if full_refresh:
        extra_command_args.append("--full-refresh")

    # Execute dbt command
    flow = Flow(trigger_dbt_cli_command.fn)
    result = flow(
        command="dbt run",
        project_dir=project_dir,
        extra_command_args=extra_command_args,
    )

    return result
