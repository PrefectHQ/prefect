import inspect
import typing
import typing as t

import pydantic
from pydantic import BaseModel as V2BaseModel
from pydantic import ConfigDict, PydanticUndefinedAnnotation, create_model
from pydantic.fields import FieldInfo
from pydantic.type_adapter import TypeAdapter

from prefect._internal.pydantic.schemas import GenerateEmptySchemaForUserClasses


def is_v2_model(v: t.Any) -> bool:
    if isinstance(v, V2BaseModel):
        return True
    try:
        if inspect.isclass(v) and issubclass(v, V2BaseModel):
            return True
    except TypeError:
        pass

    return False


def is_v2_type(v: t.Any) -> bool:
    if is_v2_model(v):
        return True

    try:
        return v.__module__.startswith("pydantic.types")
    except AttributeError:
        return False


def has_v2_type_as_param(signature: inspect.Signature) -> bool:
    parameters = signature.parameters.values()
    for p in parameters:
        # check if this parameter is a v2 model
        if is_v2_type(p.annotation):
            return True

        # check if this parameter is a collection of types
        for v in typing.get_args(p.annotation):
            if is_v2_type(v):
                return True
    return False


def process_v2_params(
    param: inspect.Parameter,
    *,
    position: int,
    docstrings: dict[str, str],
    aliases: dict[str, str],
) -> tuple[str, t.Any, t.Any]:
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

    type_ = t.Any if param.annotation is inspect.Parameter.empty else param.annotation

    existing_field = param.default if isinstance(param.default, FieldInfo) else None
    default_value = existing_field.default if existing_field else param.default
    if existing_field and existing_field.description:
        description = existing_field.description
    else:
        description = docstrings.get(param.name)

    extra: dict[str, typing.Any] = {}
    if existing_field and isinstance(existing_field.json_schema_extra, dict):
        # this will allow us to merge with the existing `json_schema_extra`
        extra.update(existing_field.json_schema_extra)

    # still ensure 'position' is always set
    extra.setdefault("position", position)

    field = pydantic.Field(
        default=... if default_value is param.empty else default_value,
        title=param.name,
        description=description,
        alias=aliases.get(name),
        json_schema_extra=extra,
    )

    return name, type_, field


def create_v2_schema(
    name_: str,
    model_cfg: t.Optional[ConfigDict] = None,
    model_base: t.Optional[type[V2BaseModel]] = None,
    model_fields: t.Optional[dict[str, t.Any]] = None,
) -> dict[str, t.Any]:
    """
    Create a pydantic v2 model and craft a v1 compatible schema from it.
    """
    model_fields = model_fields or {}
    model = create_model(
        name_, __config__=model_cfg, __base__=model_base, **model_fields
    )
    try:
        adapter = TypeAdapter(model)
    except PydanticUndefinedAnnotation as exc:
        # in v1 this raises a TypeError, which is handled by parameter_schema
        raise TypeError(exc.message)

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
