import json
import inspect
from enum import Enum
from typing import List, Dict, Any, Callable

import pendulum
import pydantic


def function_to_parameter_schema(fn: Callable) -> Dict[str, Any]:
    """Given a function, generates an OpenAPI-compatible description
    of the function's arguments by returning a schema for an object
    called "Parameters." This is the canonical representation of a
    Prefect flow's parameters.

    Args:
        fn (function): The function whose arguments will be serialized

    Returns:
        dict: the parameter schema
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
    return pydantic.create_model("Parameters", **model_fields).schema()
