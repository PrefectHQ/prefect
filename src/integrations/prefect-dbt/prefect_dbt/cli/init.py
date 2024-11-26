"""
CLI interface for dbt init command
"""
import sys
from typing import Optional

import typer
from dbt.cli.main import dbtRunner

from prefect.cli._utilities import with_cli_exception_handling
from prefect_dbt.cli.block import create_blocks_from_profile, get_profiles_dir
from prefect_dbt.cli.root import app, is_interactive


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
    cli_args = ["init"]

    if project_name:
        cli_args.append(project_name)
    if profiles_dir:
        cli_args.extend(["--profiles-dir", profiles_dir])
    if project_dir != ".":
        cli_args.extend(["--project-dir", project_dir])

    dbt = dbtRunner()
    res = dbt.invoke(cli_args)

    # Check for success
    if res.success:
        print("\nSuccessfully initialized dbt project")

        # Only prompt if in interactive mode
        if is_interactive():
            should_create_blocks = typer.confirm(
                "\nWould you like to create Prefect blocks from your dbt profile?",
                default=True,
            )

            if should_create_blocks:
                save_credentials = typer.confirm(
                    (
                        "\nIf GCP secrive account file path or service account JSON, "
                        "AWS credentials, or Snowflake credentials are found, Prefect can store them as blocks "
                        "to make your dbt profile portable. If found, would you like to create "
                        "blocks for them?"
                    ),
                    default=False,
                )
                try:
                    # Use provided profiles_dir or default
                    profiles_dir = profiles_dir or get_profiles_dir()
                    created_blocks = create_blocks_from_profile(
                        profiles_dir, save_credentials
                    )

                    if created_blocks:
                        print(f"\nSaved {len(created_blocks)} dbt CLI Profile blocks:")
                        for block_name, block_id, _ in created_blocks:
                            print(f"  - {block_name}")
                    else:
                        print(
                            "\nNo blocks were created. Please check your profiles.yml configuration."
                        )

                except Exception as e:
                    print(f"\nFailed to create blocks: {str(e)}", file=sys.stderr)
                    return False

        return True
    else:
        print("\nFailed to initialize dbt project", file=sys.stderr)
        if res.exception:
            print(f"Error: {str(res.exception)}", file=sys.stderr)
        return False
