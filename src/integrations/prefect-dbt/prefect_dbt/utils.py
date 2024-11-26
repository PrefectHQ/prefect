"""
Utility functions for prefect-dbt
"""
import os
from typing import Any, Dict, Optional

import typer
import yaml
from slugify import slugify


def get_profiles_dir() -> str:
    """Get the dbt profiles directory from environment or default location."""
    profiles_dir = os.getenv("DBT_PROFILES_DIR")
    if not profiles_dir:
        profiles_dir = os.path.expanduser("~/.dbt")
    return profiles_dir


def load_profiles_yml(profiles_dir: Optional[str]) -> Dict[str, Any]:
    """
    Load and parse the profiles.yml file.

    Args:
        profiles_dir: Path to the directory containing profiles.yml.
                     If None, uses the default profiles directory.

    Returns:
        Dict containing the parsed profiles.yml contents

    Raises:
        typer.BadParameter: If profiles.yml is not found
    """
    if profiles_dir is None:
        profiles_dir = get_profiles_dir()

    profiles_path = os.path.join(profiles_dir, "profiles.yml")
    if not os.path.exists(profiles_path):
        raise typer.BadParameter(f"No profiles.yml found at {profiles_path}")

    with open(profiles_path, "r") as f:
        return yaml.safe_load(f)


def slugify_schema(name: str, max_length: int = 45) -> Optional[str]:
    """
    Slugify text for use as a name.

    Keeps only alphanumeric characters and dashes, and caps the length
    of the slug at 45 chars.

    Args:
        name: The name of the schema

    Returns:
        The slugified job name or None if the slugified name is empty
    """
    slug = slugify(
        name,
        max_length=max_length,
        regex_pattern=r"[^a-zA-Z0-9-]+",
    )

    return slug if slug else None
