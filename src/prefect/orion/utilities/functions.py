import inspect
from typing import Any, Callable, Dict, List

import pydantic
from typing_extensions import Literal


class InputSchema(pydantic.BaseModel):
    """Simple data model corresponding to an OpenAPI `Schema`"""

    title: Literal["Inputs"] = "Inputs"
    type: Literal["object"] = "object"
    properties: Dict[str, Any] = pydantic.Field(default_factory=list)
    required: List[str] = None
    definitions: Dict[str, Any] = None

    def dict(self, *args, **kwargs):
        """Exclude `None` fields by default."""
        if "exclude_none" not in kwargs:
            kwargs["exclude_none"] = True
        return super().dict(*args, **kwargs)


def input_schema(fn: Callable) -> InputSchema:
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
    return InputSchema(**pydantic.create_model("Inputs", **model_fields).schema())
