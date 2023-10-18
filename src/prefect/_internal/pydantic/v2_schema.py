# Note: This file should only be imported under a HAS_PYDANTIC_V2 flag

import inspect
import typing as t

import pydantic
from pydantic import ConfigDict, create_model
from pydantic.type_adapter import TypeAdapter


def process_v2_params(
    position: int,
    param: inspect.Parameter,
    *,
    docstrings: t.Dict[str, str],
    aliases: t.Dict
) -> t.Tuple[str, t.Any, "pydantic.Field"]:
    """
    Generate a sanitized name, type, and pydantic.Field for a given parameter.

    This implementation is exactly the same as the v1 implementation except
    that it uses pydantic v2 constructs.
    """
    # Pydantic model creation will fail if names collide with the BaseModel type
    if hasattr(pydantic.BaseModel, param.name):
        name = param.name + "__"
        aliases[name] = param.name
    else:
        name = param.name

    type_ = t.Any if param.annotation is inspect._empty else param.annotation
    field = pydantic.Field(
        default=... if param.default is param.empty else param.default,
        title=param.name,
        description=docstrings.get(param.name, None),
        alias=aliases.get(name),
        json_schema_extra={"position": position},
    )
    return name, type_, field


def create_v2_schema(name_: str, model_cfg: ConfigDict, **model_fields):
    """
    Create a pydantic v2 model and craft a v1 compatible schema from it.
    """
    model = create_model(name_, __config__=model_cfg, **model_fields)
    adapter = TypeAdapter(model)

    # root model references under #definitions
    schema = adapter.json_schema(by_alias=True, ref_template="#/definitions/{model}")
    # ensure backwards compatability by copying $defs into definitions
    if "$defs" in schema:
        schema["definitions"] = schema["$defs"]
    return schema
