import inspect
import typing
import warnings

import pydantic
from pydantic.v1 import BaseModel as V1BaseModel


def is_v1_model(v: typing.Any) -> bool:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", category=pydantic.warnings.PydanticDeprecatedSince20
        )

        if isinstance(v, V1BaseModel):
            return True
        try:
            if inspect.isclass(v) and issubclass(v, V1BaseModel):
                return True
        except TypeError:
            pass

        return False


def is_v1_type(v: typing.Any) -> bool:
    if is_v1_model(v):
        return True

    try:
        return v.__module__.startswith("pydantic.v1.types")
    except AttributeError:
        return False


def has_v1_type_as_param(signature: inspect.Signature) -> bool:
    parameters = signature.parameters.values()
    for p in parameters:
        # check if this parameter is a v1 model
        if is_v1_type(p.annotation):
            return True

        # check if this parameter is a collection of types
        for v in typing.get_args(p.annotation):
            if is_v1_type(v):
                return True
    return False
