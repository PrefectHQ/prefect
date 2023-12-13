from typing import Any, Dict

from prefect._vendor.fastapi import FastAPI
from prefect._vendor.fastapi.openapi.utils import get_openapi

from prefect import __version__ as PREFECT_VERSION


def inject_schemas_into_openapi(
    webserver: FastAPI, deployment_schemas: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Augments the webserver's OpenAPI schema with additional schemas from deployments.

    Args:
        webserver: The FastAPI instance representing the webserver.
        deployment_schemas: A dictionary of deployment schemas to integrate.

    Returns:
        The augmented OpenAPI schema dictionary.
    """
    openapi_schema = get_openapi(
        title="FastAPI Prefect Runner", version=PREFECT_VERSION, routes=webserver.routes
    )

    merge_definitions(deployment_schemas, openapi_schema)
    update_refs_to_components(openapi_schema)

    return openapi_schema


def merge_definitions(
    deployment_schemas: Dict[str, Any], openapi_schema: Dict[str, Any]
) -> None:
    """
    Integrates definitions from deployment schemas into the OpenAPI components.

    Args:
        deployment_schemas: A dictionary of deployment-specific schemas.
        openapi_schema: The base OpenAPI schema to update.
    """
    components = openapi_schema.setdefault("components", {}).setdefault("schemas", {})
    for definitions in deployment_schemas.values():
        if "definitions" in definitions:
            for def_name, def_schema in definitions["definitions"].items():
                update_refs_in_schema(def_schema, "#/components/schemas/")
                components[def_name] = def_schema


def update_refs_in_schema(schema_item: Any, new_ref: str) -> None:
    """
    Recursively replaces `$ref` with a new reference base in a schema item.

    Args:
        schema_item: A schema or part of a schema to update references in.
        new_ref: The new base string to replace in `$ref` values.
    """
    if isinstance(schema_item, dict):
        schema_item["$ref"] = schema_item.get("$ref", "").replace(
            "#/definitions/", new_ref
        )
        for value in schema_item.values():
            update_refs_in_schema(value, new_ref)
    elif isinstance(schema_item, list):
        for item in schema_item:
            update_refs_in_schema(item, new_ref)


def update_refs_to_components(openapi_schema: Dict[str, Any]) -> None:
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
