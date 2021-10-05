"""
Utilities for working with Python functions.
"""

import inspect
from typing import Any, Callable, Dict, List

import pydantic
from typing_extensions import Literal


class ParameterSchema(pydantic.BaseModel):
    """Simple data model corresponding to an OpenAPI `Schema`."""

    title: Literal["Parameters"] = "Parameters"
    type: Literal["object"] = "object"
    properties: Dict[str, Any] = pydantic.Field(default_factory=dict)
    required: List[str] = None
    definitions: Dict[str, Any] = None

    def dict(self, *args, **kwargs):
        """Exclude `None` fields by default to comply with
        the OpenAPI spec.
        """
        kwargs.setdefault("exclude_none", True)
        return super().dict(*args, **kwargs)


def parameter_schema(fn: Callable) -> ParameterSchema:
    """Given a function, generates an OpenAPI-compatible description
    of the function's arguments, including:
        - name
        - typing information
        - whether it is required
        - a default value
        - additional constraints (like possible enum values)

    Args:
        fn (function): The function whose arguments will be serialized

    Returns:
        dict: the argument schema
    """
    signature = inspect.signature(fn)
    model_fields = {}
    for param in signature.parameters.values():
        model_fields[param.name] = (
            Any if param.annotation is inspect._empty else param.annotation,
            pydantic.Field(
                default=... if param.default is param.empty else param.default,
                title=param.name,
                description=None,
            ),
        )
    return ParameterSchema(
        **pydantic.create_model("Parameters", **model_fields).schema()
    )
