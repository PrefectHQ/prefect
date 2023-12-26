# Note: This file should only be imported under a HAS_PYDANTIC_V2 flag

import inspect
import typing
import typing as t

import pendulum
import pydantic
from pydantic import BaseModel as V2BaseModel
from pydantic import ConfigDict, create_model
from pydantic.type_adapter import TypeAdapter

from prefect._internal.pydantic.annotations.pendulum import (
    PydanticPendulumDateTimeType,
    PydanticPendulumDateType,
    PydanticPendulumDurationType,
)
from prefect._internal.pydantic.schemas import GenerateEmptySchemaForUserClasses


def _is_v2_model(v) -> bool:
    if isinstance(v, V2BaseModel):
        return True
    try:
        if inspect.isclass(v) and issubclass(v, V2BaseModel):
            return True
    except TypeError:
        pass


def has_v2_model_as_param(signature: inspect.Signature) -> bool:
    parameters = signature.parameters.values()
    for p in parameters:
        # check if this parameter is a v2 model
        if _is_v2_model(p.annotation):
            return True

        # check if this parameter is a collection of types
        for v in typing.get_args(p.annotation):
            if _is_v2_model(v):
                return True
    return False


def process_v2_params(
    param: inspect.Parameter,
    *,
    position: int,
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

    # Replace pendulum type annotations with our own so that they are pydantic compatible
    if type_ == pendulum.DateTime:
        type_ = PydanticPendulumDateTimeType
    if type_ == pendulum.Date:
        type_ = PydanticPendulumDateType
    if type_ == pendulum.Duration:
        type_ = PydanticPendulumDurationType

    field = pydantic.Field(
        default=... if param.default is param.empty else param.default,
        title=param.name,
        description=docstrings.get(param.name, None),
        alias=aliases.get(name),
        json_schema_extra={"position": position},
    )
    return name, type_, field


def create_v2_schema(
    name_: str,
    model_cfg: t.Optional[ConfigDict] = None,
    model_base: t.Optional[t.Type[V2BaseModel]] = None,
    **model_fields
):
    """
    Create a pydantic v2 model and craft a v1 compatible schema from it.
    """
    model = create_model(
        name_, __config__=model_cfg, __base__=model_base, **model_fields
    )
    adapter = TypeAdapter(model)

    # root model references under #definitions
    schema = adapter.json_schema(
        by_alias=True,
        ref_template="#/definitions/{model}",
        schema_generator=GenerateEmptySchemaForUserClasses,
    )
    # ensure backwards compatibility by copying $defs into definitions
    if "$defs" in schema:
        schema["definitions"] = schema["$defs"]
    return schema
