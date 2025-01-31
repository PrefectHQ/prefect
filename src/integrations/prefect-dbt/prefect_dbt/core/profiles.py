"""
Utilities for working with dbt profiles.yml files, including resolving
block document and variable references.
"""

import contextlib
import os
import tempfile
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    Generator,
    Optional,
)

import slugify
import yaml

from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.templating import (
    resolve_block_document_references,
    resolve_variables,
)


def get_profiles_dir() -> str:
    """Get the dbt profiles directory from environment or default location."""
    profiles_dir = os.getenv("DBT_PROFILES_DIR")
    if not profiles_dir:
        profiles_dir = os.path.expanduser("~/.dbt")
    return profiles_dir


def load_profiles_yml(profiles_dir: Optional[str]) -> dict[str, Any]:
    """
    Load and parse the profiles.yml file.

    Args:
        profiles_dir: Path to the directory containing profiles.yml.
                     If None, uses the default profiles directory.

    Returns:
        Dict containing the parsed profiles.yml contents

    Raises:
        ValueError: If profiles.yml is not found
    """
    if profiles_dir is None:
        profiles_dir = get_profiles_dir()

    profiles_path = os.path.join(profiles_dir, "profiles.yml")
    if not os.path.exists(profiles_path):
        raise ValueError(f"No profiles.yml found at {profiles_path}")

    with open(profiles_path, "r") as f:
        return yaml.safe_load(f)


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


@contextlib.asynccontextmanager
async def aresolve_profiles_yml(
    profiles_dir: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Asynchronous context manager that creates a temporary directory with a resolved profiles.yml file.

    Args:
        profiles_dir: Path to the directory containing profiles.yml.
                      If None, uses the default profiles directory.

    Yields:
        str: Path to temporary directory containing the resolved profiles.yml.
             Directory and contents are automatically cleaned up after context exit.

    Example:
    ```python
        async with aresolve_profiles_yml() as temp_dir:
            # temp_dir contains resolved profiles.yml
            # use temp_dir for dbt operations
        # temp_dir is automatically cleaned up
    ```
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        profiles_yml: dict[str, Any] = load_profiles_yml(profiles_dir)
        profiles_yml = await resolve_block_document_references(
            profiles_yml, value_transformer=replace_with_env_var_call
        )
        profiles_yml = await resolve_variables(profiles_yml)

        temp_profiles_path = temp_dir_path / "profiles.yml"
        temp_profiles_path.write_text(
            yaml.dump(profiles_yml, default_style=None, default_flow_style=False)
        )
        yield str(temp_dir_path)


@contextlib.contextmanager
def resolve_profiles_yml(
    profiles_dir: Optional[str] = None,
) -> Generator[str, None, None]:
    """
    Synchronous context manager that creates a temporary directory with a resolved profiles.yml file.

    Args:
        profiles_dir: Path to the directory containing profiles.yml.
                      If None, uses the default profiles directory.

    Yields:
        str: Path to temporary directory containing the resolved profiles.yml.
             Directory and contents are automatically cleaned up after context exit.

    Example:
    ```python
        with resolve_profiles_yml() as temp_dir:
            # temp_dir contains resolved profiles.yml
            # use temp_dir for dbt operations
        # temp_dir is automatically cleaned up
    ```
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        profiles_yml: dict[str, Any] = load_profiles_yml(profiles_dir)
        profiles_yml = run_coro_as_sync(
            resolve_block_document_references(
                profiles_yml, value_transformer=replace_with_env_var_call
            )
        )
        profiles_yml = run_coro_as_sync(resolve_variables(profiles_yml))

        temp_profiles_path = temp_dir_path / "profiles.yml"
        temp_profiles_path.write_text(
            yaml.dump(profiles_yml, default_style=None, default_flow_style=False)
        )
        yield str(temp_dir_path)
