import os
import uuid
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Dict, List, Tuple, Union

from prefect._vendor.fastapi import FastAPI
from prefect._vendor.fastapi.openapi.utils import get_openapi

from prefect import __version__ as PREFECT_VERSION
from prefect.utilities.callables import parameter_schema
from prefect.utilities.importtools import import_object

if TYPE_CHECKING:
    from prefect import Flow, Task
    from prefect.deployments import Deployment


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

    augmented_schema = merge_definitions(deployment_schemas, openapi_schema)
    return update_refs_to_components(augmented_schema)


def merge_definitions(
    deployment_schemas: Dict[str, Any], openapi_schema: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Integrates definitions from deployment schemas into the OpenAPI components.

    Args:
        deployment_schemas: A dictionary of deployment-specific schemas.
        openapi_schema: The base OpenAPI schema to update.
    """
    openapi_schema_copy = deepcopy(openapi_schema)
    components = openapi_schema_copy.setdefault("components", {}).setdefault(
        "schemas", {}
    )
    for definitions in deployment_schemas.values():
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


def _set_parameter_schema(prefect_fn: Union["Flow", "Task"]) -> Union["Flow", "Task"]:
    """
    Sets the parameter schema of a flow or task.

    Args:
        prefect_fn: The flow or task to set the parameter schema of.
        schema: The parameter schema to set.
    """
    prefect_fn.id = str(uuid.uuid4())
    prefect_fn.parameter_openapi_schema = parameter_schema(prefect_fn.fn).dict()
    prefect_fn.enforce_parameter_schema = True

    return prefect_fn


async def _find_subflows_of_deployment(
    deployment: "Deployment",
) -> List[Tuple[str, "Flow"]]:
    """
    Find all subflows of a deployment.

    Args:
        deployment: The deployment to find subflows of.

    Returns:
        A list of flows.
    """
    from prefect.deployments.base import _search_for_flow_functions

    entrypoint_dir = os.path.dirname(deployment.entrypoint.split(":")[0])

    flows = [
        entrypoint
        for flow in await _search_for_flow_functions(entrypoint_dir)
        if (entrypoint := f'{flow["filepath"]}:{flow["function_name"]}')
        != deployment.entrypoint
    ]

    return [(flow, _set_parameter_schema(import_object(flow))) for flow in flows]
