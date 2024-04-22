"""
This is a module containing generic REST tasks.
"""

# This module was auto-generated using prefect-collection-generator so
# manually editing this file is not recommended.

import json
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

import httpx

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect._internal.pydantic._compat import model_dump

if HAS_PYDANTIC_V2:
    from pydantic import BaseModel as V2BaseModel
    from pydantic.v1 import BaseModel
else:
    from pydantic import BaseModel

from prefect import task

if TYPE_CHECKING:
    from prefect_databricks import DatabricksCredentials


class HTTPMethod(Enum):
    """
    Available HTTP request methods.
    """

    GET = "get"
    POST = "post"
    PUT = "put"
    DELETE = "delete"
    PATCH = "patch"


def serialize_model(obj: Any) -> Any:
    """
    Recursively serializes `pydantic.BaseModel` into JSON;
    returns original obj if not a `BaseModel`.

    Args:
        obj: Input object to serialize.

    Returns:
        Serialized version of object.
    """
    if isinstance(obj, list):
        return [serialize_model(o) for o in obj]
    elif isinstance(obj, Dict):
        return {k: serialize_model(v) for k, v in obj.items()}

    if isinstance(obj, (BaseModel, V2BaseModel)):
        return model_dump(obj, mode="json")
    elif isinstance(obj, Enum):
        return obj.value
    return obj


def strip_kwargs(**kwargs: Dict) -> Dict:
    """
    Recursively drops keyword arguments if value is None,
    and serializes any `pydantic.BaseModel` types.

    Args:
        **kwargs: Input keyword arguments.

    Returns:
        Stripped version of kwargs.
    """
    stripped_dict = {}
    for k, v in kwargs.items():
        v = serialize_model(v)
        if isinstance(v, dict):
            v = strip_kwargs(**v)
        if v is not None:
            stripped_dict[k] = v
    return stripped_dict or {}


@task
async def execute_endpoint(
    endpoint: str,
    databricks_credentials: "DatabricksCredentials",
    http_method: HTTPMethod = HTTPMethod.GET,
    params: Dict[str, Any] = None,
    json: Dict[str, Any] = None,
    **kwargs: Dict[str, Any],
) -> httpx.Response:
    """
    Generic function for executing REST endpoints.

    Args:
        endpoint: The endpoint route.
        databricks_credentials: Credentials to use for authentication with Databricks.
        http_method: Either GET, POST, PUT, DELETE, or PATCH.
        params: URL query parameters in the request.
        json: JSON serializable object to include in the body of the request.
        **kwargs: Additional keyword arguments to pass.

    Returns:
        The httpx.Response from interacting with the endpoint.

    Examples:
        Lists jobs on the Databricks instance.
        ```python
        from prefect import flow
        from prefect_databricks import DatabricksCredentials
        from prefect_databricks.rest import execute_endpoint
        @flow
        def example_execute_endpoint_flow():
            endpoint = "/2.1/jobs/list"
            databricks_credentials = DatabricksCredentials.load("my-block")
            params = {
                "limit": 5,
                "offset": None,
                "expand_tasks": True,
            }
            response = execute_endpoint(
                endpoint,
                databricks_credentials,
                params=params
            )
            return response.json()
        ```
    """
    if isinstance(http_method, HTTPMethod):
        http_method = http_method.value

    if params is not None:
        stripped_params = strip_kwargs(**params)
    else:
        stripped_params = None

    if json is not None:
        kwargs["json"] = strip_kwargs(**json)

    async with databricks_credentials.get_client() as client:
        response = await getattr(client, http_method)(
            endpoint, params=stripped_params, **kwargs
        )

    return response


def _unpack_contents(
    response: httpx.Response, responses: Optional[Dict[int, str]] = None
) -> Union[Dict[str, Any], bytes]:
    """
    Helper method to unpack the contents from the httpx.Response,
    reporting errors in a helpful manner, if any.
    """
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        helpful_error_response = (responses or {}).get(response.status_code, "")
        try:
            helpful_error_response += f"JSON response: {response.json()}"
        except Exception:
            pass
        if helpful_error_response:
            raise httpx.HTTPStatusError(
                helpful_error_response, request=exc.request, response=exc.response
            ) from exc
        else:
            raise

    try:
        return response.json()
    except json.JSONDecodeError:
        return response.content
