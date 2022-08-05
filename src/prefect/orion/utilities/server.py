"""
Utilities for the Orion API server.
"""
import functools
import inspect
import json
from contextlib import AsyncExitStack, asynccontextmanager
from copy import deepcopy
from typing import Any, Callable, Coroutine, Iterable, List, Set, get_type_hints

import jsondiff
from fastapi import APIRouter, Request, Response, status
from fastapi.routing import APIRoute
from jsonschema.validators import RefResolver


def method_paths_from_routes(routes: Iterable[APIRoute]) -> Set[str]:
    """
    Generate a set of strings describing the given routes in the format: <method> <path>

    For example, "GET /logs/"
    """
    method_paths = set()
    for route in routes:
        for method in route.methods:
            method_paths.add(f"{method} {route.path}")

    return method_paths


def response_scoped_dependency(dependency: Callable):
    """
    Ensure that this dependency closes before the response is returned to the client. By
    default, FastAPI closes dependencies after sending the response.

    Uses an async stack that is exited before the response is returned. This is
    particularly useful for database sesssions which must be committed before the client
    can do more work.

    NOTE: Do not use a response-scoped dependency within a FastAPI background task.
          Background tasks run after FastAPI sends the response, so a response-scoped
          dependency will already be closed. Use a normal FastAPI dependency instead.

    Args:
        dependency: An async callable. FastAPI dependencies may still be used.

    Returns:
        A wrapped `dependency` which will push the `dependency` context manager onto
        a stack when called.
    """
    signature = inspect.signature(dependency)

    async def wrapper(*args, request: Request, **kwargs):
        # Replicate FastAPI behavior of auto-creating a context manager
        if inspect.isasyncgenfunction(dependency):
            context_manager = asynccontextmanager(dependency)
        else:
            context_manager = dependency

        # Ensure request is provided if requested
        if "request" in signature.parameters:
            kwargs["request"] = request

        # Enter the route handler provided stack that is closed before responding,
        # return the value yielded by the wrapped dependency
        return await request.state.response_scoped_stack.enter_async_context(
            context_manager(*args, **kwargs)
        )

    # Ensure that the signature includes `request: Request` to ensure that FastAPI will
    # inject the request as a dependency; maintain the old signature so those depends
    # work
    request_parameter = inspect.signature(wrapper).parameters["request"]
    functools.update_wrapper(wrapper, dependency)

    if "request" not in signature.parameters:
        new_parameters = signature.parameters.copy()
        new_parameters["request"] = request_parameter
        wrapper.__signature__ = signature.replace(
            parameters=tuple(new_parameters.values())
        )

    return wrapper


class OrionAPIRoute(APIRoute):
    """
    A FastAPI APIRoute class which attaches an async stack to requests that exits before
    a response is returned.

    Requests already have `request.scope['fastapi_astack']` which is an async stack for
    the full scope of the request. This stack is used for managing contexts of FastAPI
    dependencies. If we want to close a dependency before the request is complete
    (i.e. before returning a response to the user), we need a stack with a different
    scope. This extension adds this stack at `request.state.response_scoped_stack`.
    """

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        default_handler = super().get_route_handler()

        async def handle_response_scoped_depends(request: Request) -> Response:
            # Create a new stack scoped to exit before the response is returned
            async with AsyncExitStack() as stack:
                request.state.response_scoped_stack = stack
                response = await default_handler(request)

            return response

        return handle_response_scoped_depends


class OrionRouter(APIRouter):
    """
    A base class for Orion API routers.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("route_class", OrionAPIRoute)
        super().__init__(**kwargs)

    def add_api_route(
        self, path: str, endpoint: Callable[..., Any], **kwargs: Any
    ) -> None:
        """
        Add an API route.

        For routes that return content and have not specified a `response_model`,
        use return type annotation to infer the response model.

        For routes that return No-Content status codes, explicitly set
        a `response_class` to ensure nothing is returned in the response body.
        """
        if kwargs.get("status_code") == status.HTTP_204_NO_CONTENT:
            # any routes that return No-Content status codes must
            # explicilty set a response_class that will handle status codes
            # and not return anything in the body
            kwargs["response_class"] = Response
        if kwargs.get("response_model") is None:
            kwargs["response_model"] = get_type_hints(endpoint).get("return")
        return super().add_api_route(path, endpoint, **kwargs)


def compare_open_api_schemas(base: dict, revision: dict) -> str:
    """
    Compare two open API schemas and generate descriptive markdown of the changes.

    Changes should include
    - Added routes
    - Deleted routes
    - Changes in routes
        1. Changes in response schemas for 200 and 201 response codes
        2. Changes in request body schemas

    Changes detected in request/response schemas include
    - Adding a new field
    - Updating a field type
    - Deleting a field

    Args:
        base: a dictionary representing the prior state of the
            open api schema
        revision: a dictionary representing the updated state of the
            open api schema

    Returns:
        A markdown formatted string containing a human readable summary
            of the api schema changes
    """
    base_routes = _get_routes_from_schema(schema=base)
    revised_routes = _get_routes_from_schema(schema=revision)

    revision_full_schemas = _compile_full_schemas(schema=revision)
    base_full_schemas = _compile_full_schemas(schema=base)
    schema_differences = _get_schema_differences(
        base=base_full_schemas, revision=revision_full_schemas
    )

    report = "\n\n".join(
        [
            # _get_schema_differences_report(
            #     schema_differences=schema_differences,
            # ),
            _get_report_text_for_added_routes(
                added_routes=_get_added_routes(
                    base_routes=base_routes, revised_routes=revised_routes
                ),
                revised_routes=revised_routes,
            ),
            _get_report_text_for_deleted_routes(
                deleted_routes=_get_deleted_routes(
                    base_routes=base_routes, revised_routes=revised_routes
                )
            ),
            _get_route_changes_report_text(
                base_routes=base_routes,
                revised_routes=revised_routes,
                schema_differences=schema_differences,
            ),
        ]
    )

    print(report)


def _get_schema_differences_report(schema_differences: List[str]) -> str:
    """
    TODO
    """
    report_text = "## Schema updates\n"
    if len(schema_differences.keys()) == 0:
        report_text += "No schema updates found."
        return report_text
    for schema_name, explanation in schema_differences.items():
        report_text += f"**{schema_name}**\n"
        report_text += f"{explanation}\n"
    return report_text


def _compile_full_schemas(schema: dict) -> dict:
    """
    Given schemas associated with an OpenAPI spec, resolve all
    references (e.g. '#/components/schemas/ThisIsASchemaName')

    Args:
        schema: an OpenAPI schema

    Returns:
        dict: the full OpenAPI schema will references resolved
    """
    schema = deepcopy(schema)

    ref_resolver = RefResolver.from_schema(schema)
    return _resolve_nested_dict_refs(
        schemas=schema["components"]["schemas"], ref_resolver=ref_resolver
    )


def _resolve_nested_dict_refs(schemas: dict, ref_resolver: RefResolver) -> dict:
    """
    Recursively resolve references in `scchemas`

    Args:
        schemas: a subset of an OpenAPI schema
        ref_resovler: a json ref resolver used to resolve component schemas
            (e.g. '#/components/schemas/ThisIsASchemaName')
    """
    if not isinstance(schemas, dict):
        return schemas
    for k, v in schemas.items():
        if k == "$ref":
            schemas[k] = ref_resolver.resolve(v)
        elif isinstance(v, dict):
            schemas[k] = _resolve_nested_dict_refs(schemas[k], ref_resolver)
        elif isinstance(v, list):
            schemas[k] = [
                _resolve_nested_dict_refs(val, ref_resolver=ref_resolver)
                for val in schemas[k]
            ]
    return schemas


def _get_schema_differences(base: dict, revision: dict) -> dict:
    """
    TODO
    - should also probably rename args?
    """
    schema_differences = dict()

    # make copies and remove things we don't care about
    base = deepcopy(base)
    revision = deepcopy(revision)

    for schema_name, schema in revision.items():
        if schema_name in base and schema != base[schema_name]:
            schema_differences[schema_name] = _explain_schema_change(
                base_schema=base[schema_name], revision_schema=revision[schema_name]
            )
    return schema_differences


def _explain_schema_change(base_schema: dict, revision_schema: dict) -> str:
    """Generate a human readable explanation for what changed base -> revision"""

    json_diff = jsondiff.diff(
        a=base_schema,
        b=revision_schema,
        syntax="explicit",
        marshal=True,
    )

    try:
        diff_text = _explain_schema_json_diff(json_diff=json_diff, explanation="")

    except:
        diff_text = (
            "Error generating explanation. The following changes have been made:\n```json"
            + json.dumps(
                json_diff,
                indent=4,
                sort_keys=True,
            )
            + "\n```"
        )

    return diff_text


def _explain_schema_json_diff(json_diff: dict, explanation: str = "") -> str:
    """
    Given a diff between Orion API schemas, generate a human readable explanation
    for the changes.

    If an existing explanation text is given, it is assumed this is being called
    within a recursive explanation. Text will be indented accordingly.
    """
    indent = len(explanation.split("\n")[-1])

    def _write_new_indented_text(explanation: str, new_text: str, indent: int = indent):
        if not explanation.endswith("\n"):
            explanation += "\n"
        new_text = new_text.replace("\n", (" " * indent) + "\n")
        explanation += (" " * indent) + new_text
        return explanation

    property_updates = json_diff.get("$update", {}).get("properties", {})
    if property_updates:
        new_properties = property_updates.get("$insert")
        # TODO - continue here!

    enum_updates = json_diff.get("$update", {}).get("enum", {})
    if enum_updates:
        # enum insert are a list of [insert_position, val]
        # we just want the vals
        new_enum_properties = [
            insert_description[1] for insert_description in enum_updates.get("$insert")
        ]
        if new_enum_properties:
            explanation = _write_new_indented_text(
                explanation=explanation,
                new_text=f"new enum values: {','.join(new_enum_properties)}",
            )

    # inserted properties
    # updated properties
    # inserted enum


def _get_report_text_for_deleted_routes(deleted_routes: List[str]) -> str:
    """
    Given a List of deleted routes, generate report text.
    """
    report_text = "## Deleted Routes\n"
    if len(deleted_routes) == 0:
        report_text += "\nNo routes deleted"
        return report_text
    deleted_route_text_List = "\n".join(deleted_routes)
    return (
        report_text
        + f"The following routes have been deleted:\n {deleted_route_text_List}"
    )


def _get_report_text_for_added_routes(
    added_routes: List[str], revised_routes: dict
) -> str:
    """
    Given a List of added routes, generate report text.

    Args:
        added_routes: a List of routes added
        revised_routes: a dictionary containing information about
            the revised routes, this will be used to populate info
            about added routes
    """
    report_text = "## Added routes\n"
    if len(added_routes) == 0:
        report_text += "\nNo routes added."
        return report_text

    report_text += "\nThe following routes have been added:\n"
    for route in added_routes:
        report_text += f"**{route}**"
        description = revised_routes[route].get("description", "")
        report_text += f"\nDescription: {description}"
        report_text += f"\nParameters:\n{_format_parameters(revised_routes[route], revised_routes)}"

    return report_text


def _format_parameters(route: dict, ignore_headers: bool = True) -> str:
    """
    Format an OpenAPI route parameter spec in human readable text.

    Args:
        route: json representation of an OpenAPI route spec
        ignore_headers: if True, ignore any header parameters. Defaults to True.

    Returns:
        str: a human readable summary of the routes parameters, request body, and response
    """
    parameter_text = ""
    for param in route.get("parameters", []):
        if not ignore_headers or param["in"] != "header":
            param_name = param["name"]
            param_required = param["required"]
            param_location = param["in"]
            param_type = param["schema"]["type"]
            parameter_text += f"Name: {param_name}\n"
            parameter_text += f"Location: {param_location}\n"
            parameter_text += f"Required?: {param_required}\n"
            parameter_text += f"Type: {param_type}\n"
            parameter_text += "\n"

    # check for body params, note this only
    # checks for application/json types at the moment
    if route.get("requestBody"):
        parameter_text += f"Name: (request body)\nLocation: Body\nRequred?: True\n"
        # TODO - resolve refs here
        parameter_text += (
            f"Type: {route['requestBody']['content']['application/json']['schema']}\n"
        )
        parameter_text += "\n"

    # TODO - we should probably include response type in here
    return parameter_text


def _get_routes_from_schema(schema: dict) -> dict:
    """
    Extracts routes from a fast api schema.
    Outputs a dict of the form:

    {VERB /path/to/route: <route schema>}
    """
    routes = dict()
    for path in schema["paths"].keys():
        for path_op in schema["paths"][path].keys():
            routes[f"{path_op.upper()} - {path}"] = schema["paths"][path][path_op]
    return routes


def _get_deleted_routes(base_routes: dict, revised_routes: dict) -> List[str]:
    """
    Gets any routes that were deleted from `base_routes` in `revised_routes`.
    """
    deleted_routes = base_routes.keys() - revised_routes.keys()
    return deleted_routes


def _get_added_routes(base_routes: dict, revised_routes: dict) -> List[str]:
    """
    Gets any routes that were added to `revised_routes` not present in `base_routes`.
    """
    added_routes = revised_routes.keys() - base_routes.keys()
    return added_routes


def _get_route_changes_report_text(
    base_routes: dict,
    revised_routes: dict,
    schema_differences: dict,
) -> str:
    """
    Generates human readable summary of changes to API routes.

    Changes tracked will include
    - Updates to request body schema
    - Updates to 200 and/or 201 responses

    Args:
        TODO

    Returns:
        str: human readable markdown text explaining updates to routes
    """
    # TODO - this should check for schema changes too
    report_text = "## Route changes\n"
    changed_routes = {}
    for route in revised_routes:
        if route in base_routes:
            route_changes = _explain_route_changes(
                route=revised_routes[route],
                schema_differences=schema_differences,
            )
            if route_changes != "":
                changed_routes[route] = route_changes

    report_text += "\n".join(
        [
            f"**{route}**" + "\nThe following changes have been made:"
            # + "\n```json\n"
            + str(route_change)
            # + "\n```"
            for route, route_change in changed_routes.items()
        ]
    )
    return report_text


def _explain_route_changes(
    route: dict,
    schema_differences: dict,
) -> str:
    """
    Check for changes in schemas associated with a route.
    """
    explanation = ""
    # check for changes in the request body
    if (
        route.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    ):
        # handle cases where the schema is the request body
        if route["requestBody"]["content"]["application/json"]["schema"].get("$ref"):
            request_body_schema = route["requestBody"]["content"]["application/json"][
                "schema"
            ]["$ref"][len("#/components/schemas/") :]
            if request_body_schema in schema_differences:
                explanation += f"Change in request body schema {request_body_schema}:\n {schema_differences[request_body_schema]}"

        # handle cases where the schema is one item in the request body
        if (
            route["requestBody"]["content"]["application/json"]["schema"]
            .get("items", {})
            .get("$ref")
        ):
            request_body_schema = route["requestBody"]["content"]["application/json"][
                "schema"
            ]["items"]["$ref"][len("#/components/schemas/") :]
            if request_body_schema in schema_differences:
                explanation += f"Change in request body schema list[{request_body_schema}]:\n {schema_differences[request_body_schema]}"

    # check for changes in the response payload
    # TODO

    return explanation
