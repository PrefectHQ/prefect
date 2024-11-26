"""
CLI interface for dbt block commands
"""
from typing import Any, Dict, Optional

import typer

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import with_cli_exception_handling
from prefect_dbt.cli.root import app
from prefect_dbt.core import DbtCliProfile
from prefect_dbt.core.configs import (
    BigQueryTargetConfigs,
    PostgresTargetConfigs,
    SnowflakeTargetConfigs,
    TargetConfigs,
)
from prefect_dbt.utils import get_profiles_dir, load_profiles_yml, slugify_schema

TYPE_TO_CONFIG = {
    "snowflake": SnowflakeTargetConfigs,
    "bigquery": BigQueryTargetConfigs,
    "postgres": PostgresTargetConfigs,
    "redshift": PostgresTargetConfigs,  # Redshift uses Postgres configs
    "duckdb": TargetConfigs,
}

block_app = PrefectTyper(
    name="block",
    help="Commands for working with dbt blocks",
    no_args_is_help=True,
)

app.add_typer(block_app, name="block")


def create_target_configs(
    target_config: Dict[str, Any],
    profile_name: str,
    save_credentials: bool,
    output_name: Optional[str] = None,
) -> TargetConfigs:
    """Create the appropriate target configs based on the profile type."""

    adapter_type = target_config.get("type")
    if not adapter_type:
        raise ValueError("No 'type' field found in target configuration")

    config_class = TYPE_TO_CONFIG.get(adapter_type.lower())
    if not config_class:
        raise ValueError(f"Unsupported adapter type: {adapter_type}")

    target_config_blocks = config_class.create_from_profile(
        get_profiles_dir(),
        profile_name,
        output_name,
        save_credentials,
    )

    for block in target_config_blocks:
        schema_slug = slugify_schema(block.model_dump(by_alias=True).get("schema"))
        block.save(
            name=f"dbt-target-configs-{adapter_type}-{schema_slug}",
            overwrite=True,
        )
        print(
            f"Saved {adapter_type.title()} Target Configs block dbt-target-configs-{adapter_type}-{schema_slug}"
        )

    return target_config_blocks


def create_blocks_from_profile(profiles_dir: str, save_credentials: bool) -> list:
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
                target_configs_list = create_target_configs(
                    target_config, profile_name, save_credentials, target_name
                )
                for target_configs in target_configs_list:
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
    save_credentials: bool = typer.Option(
        False,
        "--save-credentials",
        help=(
            "If GCP, AWS, or Snowflake credentials are found in your dbt profile, "
            "save them as their respective block type."
        ),
    ),
):
    """
    Create new dbt CLI Profile blocks. Either create a single block with specified
    parameters or create blocks from all profiles in profiles.yml.
    """
    if from_profile:
        profiles_dir = profiles_dir or get_profiles_dir()
        created_blocks = create_blocks_from_profile(profiles_dir, save_credentials)

        print(f"\nSaved {len(created_blocks)} dbt CLI Profile blocks:")
        for block_name, block_id, _ in created_blocks:
            print(f"  - {block_name}")

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

        target_configs = create_target_configs(target_config, profile, save_credentials)

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
