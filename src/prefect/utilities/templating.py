import enum
import os
import re
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    NamedTuple,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
)

from prefect.client.utilities import inject_client
from prefect.utilities.annotations import NotSet
from prefect.utilities.collections import get_from_dict

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


T = TypeVar("T", str, int, float, bool, dict, list, None)

PLACEHOLDER_CAPTURE_REGEX = re.compile(r"({{\s*([\w\.\-\[\]$]+)\s*}})")
BLOCK_DOCUMENT_PLACEHOLDER_PREFIX = "prefect.blocks."
VARIABLE_PLACEHOLDER_PREFIX = "prefect.variables."
ENV_VAR_PLACEHOLDER_PREFIX = "$"


class PlaceholderType(enum.Enum):
    STANDARD = "standard"
    BLOCK_DOCUMENT = "block_document"
    VARIABLE = "variable"
    ENV_VAR = "env_var"


class Placeholder(NamedTuple):
    full_match: str
    name: str
    type: PlaceholderType


def determine_placeholder_type(name: str) -> PlaceholderType:
    """
    Determines the type of a placeholder based on its name.

    Args:
        name: The name of the placeholder

    Returns:
        The type of the placeholder
    """
    if name.startswith(BLOCK_DOCUMENT_PLACEHOLDER_PREFIX):
        return PlaceholderType.BLOCK_DOCUMENT
    elif name.startswith(VARIABLE_PLACEHOLDER_PREFIX):
        return PlaceholderType.VARIABLE
    elif name.startswith(ENV_VAR_PLACEHOLDER_PREFIX):
        return PlaceholderType.ENV_VAR
    else:
        return PlaceholderType.STANDARD


def find_placeholders(template: T) -> Set[Placeholder]:
    """
    Finds all placeholders in a template.

    Args:
        template: template to discover placeholders in

    Returns:
        A set of all placeholders in the template
    """
    if isinstance(template, (int, float, bool)):
        return set()
    if isinstance(template, str):
        result = PLACEHOLDER_CAPTURE_REGEX.findall(template)
        return {
            Placeholder(full_match, name, determine_placeholder_type(name))
            for full_match, name in result
        }
    elif isinstance(template, dict):
        return set().union(
            *[find_placeholders(value) for key, value in template.items()]
        )
    elif isinstance(template, list):
        return set().union(*[find_placeholders(item) for item in template])
    else:
        raise ValueError(f"Unexpected type: {type(template)}")


def apply_values(
    template: T, values: Dict[str, Any], remove_notset: bool = True
) -> Union[T, Type[NotSet]]:
    """
    Replaces placeholders in a template with values from a supplied dictionary.

    Will recursively replace placeholders in dictionaries and lists.

    If a value has no placeholders, it will be returned unchanged.

    If a template contains only a single placeholder, the placeholder will be
    fully replaced with the value.

    If a template contains text before or after a placeholder or there are
    multiple placeholders, the placeholders will be replaced with the
    corresponding variable values.

    If a template contains a placeholder that is not in `values`, NotSet will
    be returned to signify that no placeholder replacement occurred. If
    `template` is a dictionary that contains a key with a value of NotSet,
    the key will be removed in the return value unless `remove_notset` is set to False.

    Args:
        template: template to discover and replace values in
        values: The values to apply to placeholders in the template
        remove_notset: If True, remove keys with an unset value

    Returns:
        The template with the values applied
    """
    if isinstance(template, (int, float, bool, type(NotSet), type(None))):
        return template
    if isinstance(template, str):
        placeholders = find_placeholders(template)
        if not placeholders:
            # If there are no values, we can just use the template
            return template
        elif (
            len(placeholders) == 1
            and list(placeholders)[0].full_match == template
            and list(placeholders)[0].type is PlaceholderType.STANDARD
        ):
            # If there is only one variable with no surrounding text,
            # we can replace it. If there is no variable value, we
            # return NotSet to indicate that the value should not be included.
            return get_from_dict(values, list(placeholders)[0].name, NotSet)
        else:
            for full_match, name, placeholder_type in placeholders:
                if placeholder_type is PlaceholderType.STANDARD:
                    value = get_from_dict(values, name, NotSet)
                elif placeholder_type is PlaceholderType.ENV_VAR:
                    name = name.lstrip(ENV_VAR_PLACEHOLDER_PREFIX)
                    value = os.environ.get(name, NotSet)
                else:
                    continue

                if value is NotSet and not remove_notset:
                    continue
                elif value is NotSet:
                    template = template.replace(full_match, "")
                else:
                    template = template.replace(full_match, str(value))

            return template
    elif isinstance(template, dict):
        updated_template = {}
        for key, value in template.items():
            updated_value = apply_values(value, values, remove_notset=remove_notset)
            if updated_value is not NotSet:
                updated_template[key] = updated_value
            elif not remove_notset:
                updated_template[key] = value

        return updated_template
    elif isinstance(template, list):
        updated_list = []
        for value in template:
            updated_value = apply_values(value, values, remove_notset=remove_notset)
            if updated_value is not NotSet:
                updated_list.append(updated_value)
        return updated_list
    else:
        raise ValueError(f"Unexpected template type {type(template).__name__!r}")


@inject_client
async def resolve_block_document_references(
    template: T, client: "PrefectClient" = None
) -> Union[T, Dict[str, Any]]:
    """
    Resolve block document references in a template by replacing each reference with
    the data of the block document.

    Recursively searches for block document references in dictionaries and lists.

    Identifies block document references by the as dictionary with the following
    structure:
    ```
    {
        "$ref": {
            "block_document_id": <block_document_id>
        }
    }
    ```
    where `<block_document_id>` is the ID of the block document to resolve.

    Once the block document is retrieved from the API, the data of the block document
    is used to replace the reference.

    Accessing Values:
    -----------------
    To access different values in a block document, use dot notation combined with the block document's prefix, slug, and block name.

    For a block document with the structure:
    ```json
    {
        "value": {
            "key": {
                "nested-key": "nested-value"
            },
            "list": [
                {"list-key": "list-value"},
                1,
                2
            ]
        }
    }
    ```
    examples of value resolution are as follows:

    1. Accessing a nested dictionary:
       Format: prefect.blocks.<block_type_slug>.<block_document_name>.value.key
       Example: Returns {"nested-key": "nested-value"}

    2. Accessing a specific nested value:
       Format: prefect.blocks.<block_type_slug>.<block_document_name>.value.key.nested-key
       Example: Returns "nested-value"

    3. Accessing a list element's key-value:
       Format: prefect.blocks.<block_type_slug>.<block_document_name>.value.list[0].list-key
       Example: Returns "list-value"

    Default Resolution for System Blocks:
    -------------------------------------
    For system blocks, which only contain a `value` attribute, this attribute is resolved by default.

    Args:
        template: The template to resolve block documents in

    Returns:
        The template with block documents resolved
    """
    if isinstance(template, dict):
        block_document_id = template.get("$ref", {}).get("block_document_id")
        if block_document_id:
            block_document = await client.read_block_document(block_document_id)
            return block_document.data
        updated_template = {}
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
        if len(placeholders) == 0 or not has_block_document_placeholder:
            return template
        elif (
            len(placeholders) == 1
            and list(placeholders)[0].full_match == template
            and list(placeholders)[0].type is PlaceholderType.BLOCK_DOCUMENT
        ):
            # value_keypath will be a list containing a dot path if additional
            # attributes are accessed and an empty list otherwise.
            block_type_slug, block_document_name, *value_keypath = (
                list(placeholders)[0]
                .name.replace(BLOCK_DOCUMENT_PLACEHOLDER_PREFIX, "")
                .split(".", 2)
            )
            block_document = await client.read_block_document_by_name(
                name=block_document_name, block_type_slug=block_type_slug
            )
            value = block_document.data

            # resolving system blocks to their data for backwards compatibility
            if len(value) == 1 and "value" in value:
                # only resolve the value if the keypath is not already pointing to "value"
                if len(value_keypath) == 0 or value_keypath[0][:5] != "value":
                    value = value["value"]

            # resolving keypath/block attributes
            if len(value_keypath) > 0:
                value_keypath: str = value_keypath[0]
                value = get_from_dict(value, value_keypath, default=NotSet)
                if value is NotSet:
                    raise ValueError(
                        f"Invalid template: {template!r}. Could not resolve the"
                        " keypath in the block document data."
                    )

            return value
        else:
            raise ValueError(
                f"Invalid template: {template!r}. Only a single block placeholder is"
                " allowed in a string and no surrounding text is allowed."
            )

    return template


@inject_client
async def resolve_variables(template: T, client: Optional["PrefectClient"] = None):
    """
    Resolve variables in a template by replacing each variable placeholder with the
    value of the variable.

    Recursively searches for variable placeholders in dictionaries and lists.

    Strips variable placeholders if the variable is not found.

    Args:
        template: The template to resolve variables in

    Returns:
        The template with variables resolved
    """
    if isinstance(template, str):
        placeholders = find_placeholders(template)
        has_variable_placeholder = any(
            placeholder.type is PlaceholderType.VARIABLE for placeholder in placeholders
        )
        if not placeholders or not has_variable_placeholder:
            # If there are no values, we can just use the template
            return template
        elif (
            len(placeholders) == 1
            and list(placeholders)[0].full_match == template
            and list(placeholders)[0].type is PlaceholderType.VARIABLE
        ):
            variable_name = list(placeholders)[0].name.replace(
                VARIABLE_PLACEHOLDER_PREFIX, ""
            )
            variable = await client.read_variable_by_name(name=variable_name)
            if variable is None:
                return ""
            else:
                return variable.value
        else:
            for full_match, name, placeholder_type in placeholders:
                if placeholder_type is PlaceholderType.VARIABLE:
                    variable_name = name.replace(VARIABLE_PLACEHOLDER_PREFIX, "")
                    variable = await client.read_variable_by_name(name=variable_name)
                    if variable is None:
                        template = template.replace(full_match, "")
                    else:
                        template = template.replace(full_match, variable.value)
            return template
    elif isinstance(template, dict):
        return {
            key: await resolve_variables(value, client=client)
            for key, value in template.items()
        }
    elif isinstance(template, list):
        return [await resolve_variables(item, client=client) for item in template]
    else:
        return template
