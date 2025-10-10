"""
Utility functions for prefect-dbt
"""

import os
from pathlib import Path
from typing import Any, Optional

import slugify

from prefect.types.names import (
    MAX_ASSET_KEY_LENGTH,
    RESTRICTED_ASSET_CHARACTERS,
)


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
        The formatted asset key
    """
    relation_name = relation_name.replace('"', "").replace(".", "/")
    for char in RESTRICTED_ASSET_CHARACTERS:
        relation_name = relation_name.replace(char, "")

    asset_key = f"{adapter_type}://{relation_name}"

    if len(asset_key) > MAX_ASSET_KEY_LENGTH:
        asset_key = asset_key[:MAX_ASSET_KEY_LENGTH]

    return asset_key


def kwargs_to_args(kwargs: dict, args: Optional[list[str]] = None) -> list[str]:
    """
    Convert a dictionary of kwargs to a list of args in the dbt CLI format.
    If args are provided, they take priority over kwargs when conflicts exist.

    Args:
        kwargs: A dictionary of kwargs.
        args: Optional list of existing args that take priority over kwargs.

    Returns:
        A list of args.
    """
    if args is None:
        args = []

    kwargs_args = []
    for key, value in list(kwargs.items()):
        if value is None:
            continue

        flag = "--" + key.replace("_", "-")

        if isinstance(value, bool):
            kwargs_args.append(flag if value else f"--no-{key.replace('_', '-')}")

        elif isinstance(value, (list, tuple)):
            kwargs_args.append(flag)
            kwargs_args.extend(str(v) for v in value)
        else:
            kwargs_args.extend([flag, str(value)])

        kwargs.pop(key)

    existing_flags = _parse_args_to_flag_groups(args)
    kwargs_flags = _parse_args_to_flag_groups(kwargs_args)

    result_args = []

    # First add positional arguments (like the dbt command)
    if "__positional__" in existing_flags:
        result_args.extend(existing_flags["__positional__"])
        del existing_flags["__positional__"]

    # Then add flags from existing args
    for flag, values in existing_flags.items():
        result_args.extend([flag] + values)

    # Finally add flags from kwargs that aren't already in existing args
    for flag, values in kwargs_flags.items():
        if flag not in existing_flags:
            result_args.extend([flag] + values)

    return result_args


def _parse_args_to_flag_groups(args_list: list[str]) -> dict[str, list[str]]:
    groups = {}
    current_flag = None
    positional = []

    for arg in args_list:
        if arg.startswith("--"):
            current_flag = arg
            groups[current_flag] = []
        elif current_flag:
            groups[current_flag].append(arg)
        else:
            # This is a positional argument (like the dbt command)
            positional.append(arg)

    # Store positional args with a special key
    if positional:
        groups["__positional__"] = positional

    return groups
