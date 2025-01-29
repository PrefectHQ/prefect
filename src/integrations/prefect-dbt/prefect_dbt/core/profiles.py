"""
Utilities for working with dbt profiles.yml files, including resolving 
block document and variable references.
"""

import contextlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, TypeVar, Union

import slugify
import yaml

from prefect.client.utilities import inject_client
from prefect.utilities.annotations import NotSet
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.collections import get_from_dict
from prefect.utilities.templating import (
    PlaceholderType,
    find_placeholders,
    resolve_variables,
)

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


T = TypeVar("T", str, int, float, bool, dict[Any, Any], list[Any], None)

BLOCK_DOCUMENT_PLACEHOLDER_PREFIX = "prefect.blocks."


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


@contextlib.asynccontextmanager
async def aresolve_profiles_yml(profiles_dir: Optional[str] = None):
    """
    Asynchronous context manager that creates a temporary directory with a resolved profiles.yml file.

    Args:
        profiles_dir: Path to the directory containing profiles.yml.
                     If None, uses the default profiles directory.

    Yields:
        str: Path to temporary directory containing the resolved profiles.yml.
            Directory and contents are automatically cleaned up after context exit.

    Example:        ```python
        async with aresolve_profiles_yml() as temp_dir:
            # temp_dir contains resolved profiles.yml
            # use temp_dir for dbt operations
        # temp_dir is automatically cleaned up        ```
    """
    temp_dir = Path(tempfile.mkdtemp())
    try:
        profiles_yml: dict[str, Any] = load_profiles_yml(profiles_dir)
        profiles_yml = await resolve_block_document_references(profiles_yml)
        profiles_yml = await resolve_variables(profiles_yml)

        temp_profiles_path = temp_dir / "profiles.yml"
        temp_profiles_path.write_text(yaml.dump(profiles_yml, default_flow_style=False))

        yield str(temp_dir)
    finally:
        shutil.rmtree(temp_dir)


@contextlib.contextmanager
def resolve_profiles_yml(profiles_dir: Optional[str] = None):
    """
    Synchronous context manager that creates a temporary directory with a resolved profiles.yml file.

    Args:
        profiles_dir: Path to the directory containing profiles.yml.
                     If None, uses the default profiles directory.

    Yields:
        str: Path to temporary directory containing the resolved profiles.yml.
            Directory and contents are automatically cleaned up after context exit.

    Example:        ```python
        with resolve_profiles_yml() as temp_dir:
            # temp_dir contains resolved profiles.yml
            # use temp_dir for dbt operations
        # temp_dir is automatically cleaned up        ```
    """
    temp_dir = Path(tempfile.mkdtemp())
    try:
        profiles_yml: dict[str, Any] = load_profiles_yml(profiles_dir)
        profiles_yml = run_coro_as_sync(resolve_block_document_references(profiles_yml))
        profiles_yml = run_coro_as_sync(resolve_variables(profiles_yml))

        temp_profiles_path = temp_dir / "profiles.yml"
        temp_profiles_path.write_text(
            yaml.dump(profiles_yml, default_style=None, default_flow_style=False)
        )

        yield str(temp_dir)
    finally:
        shutil.rmtree(temp_dir)


@inject_client
async def resolve_block_document_references(
    template: T, client: Optional["PrefectClient"] = None
) -> Union[T, dict[str, Any]]:
    """
    Resolve block document references in a template by replacing each reference with
    template text that calls dbt's env_var function, like
    {{ env_var('PREFECT_BLOCK_SECRET_MYSECRET') }}. Creates environment variables
    for each block document reference, with a name in the format
    PREFECT_BLOCKS_BLOCK_TYPE_SLUG_BLOCK_DOCUMENT_NAME and optionally BLOCK_DOCUMENT_KEYPATH.

    Recursively searches for block document references in dictionaries and lists.

    Args:
        template: The template to resolve block documents in

    Returns:
        The template with block documents resolved
    """
    if TYPE_CHECKING:
        # The @inject_client decorator takes care of providing the client, but
        # the function signature must mark it as optional to callers.
        assert client is not None

    if isinstance(template, dict):
        block_document_id = template.get("$ref", {}).get("block_document_id")
        if block_document_id:
            block_document = await client.read_block_document(block_document_id)
            return block_document.data
        updated_template: dict[str, Any] = {}
        for key, value in template.items():
            updated_value = await resolve_block_document_references(
                value, client=client
            )
            updated_template[key] = updated_value
        return updated_template
    elif isinstance(template, list):
        return [
            await resolve_block_document_references(item, client=client)
            for item in template
        ]
    elif isinstance(template, str):
        placeholders = find_placeholders(template)
        has_block_document_placeholder = any(
            placeholder.type is PlaceholderType.BLOCK_DOCUMENT
            for placeholder in placeholders
        )
        if not (placeholders and has_block_document_placeholder):
            return template
        elif (
            len(placeholders) == 1
            and list(placeholders)[0].full_match == template
            and list(placeholders)[0].type is PlaceholderType.BLOCK_DOCUMENT
        ):
            # value_keypath will be a list containing a dot path if additional
            # attributes are accessed and an empty list otherwise.
            [placeholder] = placeholders
            parts = placeholder.name.replace(
                BLOCK_DOCUMENT_PLACEHOLDER_PREFIX, ""
            ).split(".", 2)
            block_type_slug, block_document_name, *value_keypath = parts
            block_document = await client.read_block_document_by_name(
                name=block_document_name, block_type_slug=block_type_slug
            )
            data = block_document.data
            value: Union[T, dict[str, Any]] = data

            # resolving system blocks to their data for backwards compatibility
            if len(data) == 1 and "value" in data:
                # only resolve the value if the keypath is not already pointing to "value"
                if not (value_keypath and value_keypath[0].startswith("value")):
                    data = value = value["value"]

            # resolving keypath/block attributes
            if value_keypath:
                from_dict: Any = get_from_dict(data, value_keypath[0], default=NotSet)
                if from_dict is NotSet:
                    raise ValueError(
                        f"Invalid template: {template!r}. Could not resolve the"
                        " keypath in the block document data."
                    )
                value = from_dict

            env_var_name = slugify.slugify(placeholder[0], separator="_").upper()

            os.environ[env_var_name] = str(value)

            template_text = f"{{{{ env_var('{env_var_name}') }}}}"

            return template_text
        else:
            raise ValueError(
                f"Invalid template: {template!r}. Only a single block placeholder is"
                " allowed in a string and no surrounding text is allowed."
            )

    return template
