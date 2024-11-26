"""
CLI interface for dbt block commands
"""
import os
from typing import Any, Dict, Optional

import typer
import yaml
from slugify import slugify

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import with_cli_exception_handling
from prefect_dbt._cli.root import app
from prefect_dbt.cli import DbtCliProfile
from prefect_dbt.cli.configs import (
    BigQueryTargetConfigs,
    PostgresTargetConfigs,
    SnowflakeTargetConfigs,
    TargetConfigs,
)

block_app = PrefectTyper(
    name="block",
    help="Commands for working with dbt blocks",
    no_args_is_help=True,
)

app.add_typer(block_app, name="block")


def slugify_name(name: str, max_length: int = 45) -> Optional[str]:
    """
    Slugify text for use as a name.

    Keeps only alphanumeric characters and dashes, and caps the length
    of the slug at 45 chars.

    Args:
        name: The name of the job

    Returns:
        The slugified job name or None if the slugified name is empty
    """
    slug = slugify(
        name,
        max_length=max_length,  # Leave enough space for generateName
        regex_pattern=r"[^a-zA-Z0-9-]+",
    )

    return slug if slug else None


def get_profiles_dir() -> str:
    """Get the dbt profiles directory from environment or default location."""
    profiles_dir = os.getenv("DBT_PROFILES_DIR")
    if not profiles_dir:
        profiles_dir = os.path.expanduser("~/.dbt")
    return profiles_dir


def load_profiles_yml(profiles_dir: str) -> dict:
    """Load and parse the profiles.yml file."""
    profiles_path = os.path.join(profiles_dir, "profiles.yml")
    if not os.path.exists(profiles_path):
        raise typer.BadParameter(f"No profiles.yml found at {profiles_path}")

    with open(profiles_path, "r") as f:
        return yaml.safe_load(f)


def create_target_configs(target_config: Dict[str, Any]) -> TargetConfigs:
    """Create the appropriate target configs based on the profile type."""
    type_to_config = {
        "snowflake": SnowflakeTargetConfigs,
        "bigquery": BigQueryTargetConfigs,
        "postgres": PostgresTargetConfigs,
        "redshift": PostgresTargetConfigs,  # Redshift uses Postgres configs
        "duckdb": TargetConfigs,
    }

    adapter_type = target_config.get("type")
    if not adapter_type:
        raise ValueError("No 'type' field found in target configuration")

    config_class = type_to_config.get(adapter_type.lower())
    if not config_class:
        raise ValueError(f"Unsupported adapter type: {adapter_type}")

    target_dict = target_config.copy()
    schema = (
        target_dict.get("schema")
        if adapter_type != "duckdb"
        else target_dict.get("path")
    )

    target_config_block = config_class(type=adapter_type, schema=schema)
    target_config_block.save(
        name=f"dbt-target-configs-{adapter_type}-{slugify_name(schema)}", overwrite=True
    )

    return target_config_block


def create_blocks_from_profile(profiles_dir: str) -> list:
    """Create blocks from all profiles in profiles.yml."""
    profiles = load_profiles_yml(profiles_dir)
    created_blocks = []

    for profile_name, profile_data in profiles.items():
        # Skip config section if present
        if profile_name == "config":
            continue

        # Handle each target in the profile
        for target_name, target_config in profile_data.get("outputs", {}).items():
            block_name = f"dbt-{profile_name}-{target_name}"

            try:
                target_configs = create_target_configs(target_config)

                block = DbtCliProfile(
                    name=block_name,
                    profiles_dir=profiles_dir,
                    profile=profile_name,
                    target=target_name,
                    target_configs=target_configs,
                )

                block_id = block.save(block_name, overwrite=True)
                created_blocks.append((block_name, block_id, block))

            except (ValueError, TypeError) as e:
                print(f"Warning: Skipping {block_name} - {str(e)}")
                continue

    return created_blocks


@block_app.command()
@with_cli_exception_handling
def create(
    ctx: typer.Context,
    name: str = typer.Option(
        None,
        "--name",
        "-n",
        help="The name to give to the block",
    ),
    profiles_dir: str = typer.Option(
        None,
        "--profiles-dir",
        help="Path to the profiles directory containing profiles.yml",
    ),
    profile: str = typer.Option(
        None,
        "--profile",
        help="The dbt profile name to use",
    ),
    target: Optional[str] = typer.Option(
        None,
        "--target",
        help="The dbt target name to use (optional)",
    ),
    project_dir: Optional[str] = typer.Option(
        None,
        "--project-dir",
        help="Path to the dbt project directory (optional)",
    ),
    from_profile: bool = typer.Option(
        False,
        "--from-profile",
        help="Create blocks from all profiles in profiles.yml",
    ),
):
    """
    Create new dbt CLI Profile blocks. Either create a single block with specified
    parameters or create blocks from all profiles in profiles.yml.
    """
    if from_profile:
        profiles_dir = profiles_dir or get_profiles_dir()
        created_blocks = create_blocks_from_profile(profiles_dir)

        print(f"\nCreated {len(created_blocks)} dbt CLI Profile blocks:")
        for block_name, block_id, block in created_blocks:
            print(f"\nBlock: {block_name}")

        return [block_id for _, block_id, _ in created_blocks]

    else:
        if not all([name, profiles_dir, profile]):
            raise typer.BadParameter(
                "When not using --from-profile, you must specify --name, "
                "--profiles-dir, and --profile"
            )

        # Load profile to get target configs
        profiles = load_profiles_yml(profiles_dir)
        profile_data = profiles.get(profile)
        if not profile_data:
            raise typer.BadParameter(f"Profile {profile} not found in profiles.yml")

        target = target or profile_data.get("target")
        if not target:
            raise typer.BadParameter(
                "No target specified and no default target found in profile"
            )

        target_config = profile_data.get("outputs", {}).get(target)
        if not target_config:
            raise typer.BadParameter(f"Target {target} not found in profile {profile}")

        target_configs = create_target_configs(target_config)

        block = DbtCliProfile(
            name=name,
            profiles_dir=profiles_dir,
            profile=profile,
            target=target,
            target_configs=target_configs,
            project_dir=project_dir,
        )

        block_id = block.save(name, overwrite=True)

        print(f"\nCreated dbt CLI Profile block '{name}' ({block_id})")
        # print("Details:")
        # print(block.name)

        # return block_id
