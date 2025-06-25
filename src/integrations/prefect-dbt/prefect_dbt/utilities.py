"""
Utility functions for prefect-dbt
"""

import os
from pathlib import Path
from typing import Any

import slugify


def find_profiles_dir() -> Path:
    """
    Find the directory containing profiles.yml.

    Returns the current working directory if profiles.yml exists there,
    otherwise returns the default .dbt directory in the user's home.

    Returns:
        Path: Directory containing profiles.yml
    """
    cwd = Path.cwd()
    if (cwd / "profiles.yml").exists():
        return cwd
    return Path.home() / ".dbt"


def replace_with_env_var_call(placeholder: str, value: Any) -> str:
    """
    A block reference replacement function that returns template text for an env var call.

    Args:
        placeholder: The placeholder text to replace
        value: The value to replace the placeholder with

    Returns:
        The template text for an env var call
    """
    env_var_name = slugify.slugify(placeholder, separator="_").upper()

    os.environ[env_var_name] = str(value)

    template_text = f"{{{{ env_var('{env_var_name}') }}}}"

    return template_text


def format_resource_id(adapter_type: str, relation_name: str) -> str:
    """
    Format a relation name to be a valid asset key.

    Args:
        adapter_type: The type of adapter used to connect to the database
        relation_name: The name of the relation to format

    Returns:
        The formatted relation name
    """
    relation_name = relation_name.replace('"', "").replace(".", "/")
    return f"{adapter_type}://{relation_name}"
