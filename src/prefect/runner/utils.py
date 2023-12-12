import typing as t

from prefect._vendor.fastapi import FastAPI
from prefect._vendor.fastapi.openapi.utils import get_openapi


def _inject_schemas_into_generated_openapi(
    webserver: FastAPI, schemas: t.Dict[str, t.Any]
) -> t.Dict[str, t.Any]:
    """Injects the parameter schemas into the Runner's Webserver OpenAPI schema

    Args:
        - webserver: the webserver to inject the schemas into
        - schemas: the schemas to inject
    """
    openapi_schema = get_openapi(
        title="FastAPI Prefect Runner", version="2.5.0", routes=webserver.routes
    )

    # Update the components/schemas with definitions from the deployment schemas
    _merge_definitions_into_components(schemas, openapi_schema)

    # Update the paths with correct references based on the components
    _update_paths_with_correct_refs(openapi_schema)

    return openapi_schema


def _merge_definitions_into_components(
    input_schemas: t.Dict[str, t.Any], openapi_schema: t.Dict[str, t.Any]
) -> None:
    """Merges the input schemas into the OpenAPI schema's components/schemas

    Args:
        - input_schemas: the schemas to merge into the OpenAPI schema
        - openapi_schema: the OpenAPI schema to merge the schemas into
    """
    components_schemas = openapi_schema.setdefault("components", {}).setdefault(
        "schemas", {}
    )
    for schema in input_schemas.values():
        if "definitions" in schema:
            for def_name, def_value in schema["definitions"].items():
                # Recursively update all $ref in the schema definition
                _recursively_update_refs(def_value, "#/components/schemas/")
                components_schemas[def_name] = def_value


def _recursively_update_refs(item: t.Any, new_ref_base: str) -> None:
    """Recursively updates all $ref in the item

    Args:
        - item: the item to update
        - new_ref_base: the new $ref base to use
    """
    if isinstance(item, dict):
        if "$ref" in item:
            item["$ref"] = item["$ref"].replace("#/definitions/", new_ref_base)
        for value in item.values():
            _recursively_update_refs(value, new_ref_base)
    elif isinstance(item, list):
        for i in item:
            _recursively_update_refs(i, new_ref_base)


def _update_paths_with_correct_refs(openapi_schema: t.Dict[str, t.Any]) -> None:
    """Updates the paths with the correct $ref values

    Args:
        - openapi_schema: the OpenAPI schema to update the paths for
    """
    for path_item in openapi_schema.get("paths", {}).values():
        for method in path_item.values():
            if "requestBody" in method:
                content = (
                    method["requestBody"].get("content", {}).get("application/json", {})
                )
                if "schema" in content:
                    _recursively_update_refs(content["schema"], "#/components/schemas/")
