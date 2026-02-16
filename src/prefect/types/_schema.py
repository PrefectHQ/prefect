"""Types for OpenAPI schemas."""

from typing import Annotated, Any

from pydantic import BeforeValidator


def _normalize_parameter_schema(value: Any) -> dict[str, Any]:
    """
    Normalize empty or None parameter schemas to valid OpenAPI format.

    Ensures parameter_openapi_schema is always a valid OpenAPI object schema,
    converting None or {} to {"type": "object", "properties": {}}.
    """
    if value is None or value == {}:
        return {"type": "object", "properties": {}}
    return value


ParameterSchema = Annotated[
    dict[str, Any],
    BeforeValidator(_normalize_parameter_schema),
]
