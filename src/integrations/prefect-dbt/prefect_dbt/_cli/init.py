"""
CLI interface for dbt init command
"""
import sys
from typing import Optional

import typer
from dbt.cli.main import dbtRunner

from prefect.cli._utilities import with_cli_exception_handling
from prefect_dbt._cli.root import app


@app.command()
@with_cli_exception_handling
def init(
    ctx: typer.Context,
    project_name: Optional[str] = typer.Argument(
        None,
        help="Name of the new dbt project",
    ),
    project_dir: str = typer.Option(
        ".",
        "--project-dir",
        help="The directory to initialize the project in",
    ),
    profiles_dir: Optional[str] = typer.Option(
        None,
        "--profiles-dir",
        help="The directory containing profiles.yml",
    ),
):
    """
    Initialize a new dbt project. This will create a new dbt project with example
    models and configurations.
    """
    # Build command args
    cli_args = ["init"]

    if project_name:
        cli_args.append(project_name)
    if profiles_dir:
        cli_args.extend(["--profiles-dir", profiles_dir])
    if project_dir != ".":
        cli_args.extend(["--project-dir", project_dir])

    # Create dbt runner
    dbt = dbtRunner()

    # Run init command
    res = dbt.invoke(cli_args)

    # Check for success
    if res.success:
        print("\nSuccessfully initialized dbt project")
        return True
    else:
        print("\nFailed to initialize dbt project", file=sys.stderr)
        if res.exception:
            print(f"Error: {str(res.exception)}", file=sys.stderr)
        return False
