from copy import deepcopy
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from prefect import __version__ as PREFECT_VERSION


def inject_schemas_into_openapi(
    webserver: FastAPI, schemas_to_inject: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Augments the webserver's OpenAPI schema with additional schemas from deployments / flows / tasks.

    Args:
        webserver: The FastAPI instance representing the webserver.
        schemas_to_inject: A dictionary of OpenAPI schemas to integrate.

    Returns:
        The augmented OpenAPI schema dictionary.
    """
    openapi_schema = get_openapi(
        title="FastAPI Prefect Runner", version=PREFECT_VERSION, routes=webserver.routes
    )

    augmented_schema = merge_definitions(schemas_to_inject, openapi_schema)
    return update_refs_to_components(augmented_schema)


def merge_definitions(
    injected_schemas: Dict[str, Any], openapi_schema: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Integrates definitions from injected schemas into the OpenAPI components.

    Args:
        injected_schemas: A dictionary of deployment-specific schemas.
        openapi_schema: The base OpenAPI schema to update.
    """
    openapi_schema_copy = deepcopy(openapi_schema)
    components = openapi_schema_copy.setdefault("components", {}).setdefault(
        "schemas", {}
    )
    for definitions in injected_schemas.values():
        if "definitions" in definitions:
            for def_name, def_schema in definitions["definitions"].items():
                def_schema_copy = deepcopy(def_schema)
                update_refs_in_schema(def_schema_copy, "#/components/schemas/")
                components[def_name] = def_schema_copy
    return openapi_schema_copy


def update_refs_in_schema(schema_item: Any, new_ref: str) -> None:
    """
    Recursively replaces `$ref` with a new reference base in a schema item.

    Args:
        schema_item: A schema or part of a schema to update references in.
        new_ref: The new base string to replace in `$ref` values.
    """
    if isinstance(schema_item, dict):
        if "$ref" in schema_item:
            schema_item["$ref"] = schema_item["$ref"].replace("#/definitions/", new_ref)
        for value in schema_item.values():
            update_refs_in_schema(value, new_ref)
    elif isinstance(schema_item, list):
        for item in schema_item:
            update_refs_in_schema(item, new_ref)


def update_refs_to_components(openapi_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updates all `$ref` fields in the OpenAPI schema to reference the components section.

    Args:
        openapi_schema: The OpenAPI schema to modify `$ref` fields in.
    """
    for path_item in openapi_schema.get("paths", {}).values():
        for operation in path_item.values():
            schema = (
                operation.get("requestBody", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema", {})
            )
            update_refs_in_schema(schema, "#/components/schemas/")

    for definition in openapi_schema.get("definitions", {}).values():
        update_refs_in_schema(definition, "#/components/schemas/")

    return openapi_schema
