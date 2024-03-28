from functools import partial
from typing import Any, Callable, Generic, Type, TypeVar, cast, overload

from prefect._internal.pydantic._flags import HAS_PYDANTIC_V2, USE_PYDANTIC_V2
from prefect._internal.pydantic.type_dispatch import (
    v1_add_type_dispatch,
    v2_add_type_dispatch,
)

if HAS_PYDANTIC_V2:
    import pydantic.v1 as pydantic
else:
    import pydantic

from jsonpatch import JsonPatch as JsonPatchBase

from prefect.utilities.importtools import from_qualified_name, to_qualified_name

D = TypeVar("D", bound=Any)
M = TypeVar("M", bound=pydantic.BaseModel)


def _reduce_model(model: pydantic.BaseModel):
    """
    Helper for serializing a cythonized model with cloudpickle.

    Keyword arguments can provide additional settings to the `json` call. Since
    `__reduce__` takes no arguments, these are set on the `__reduce_kwargs__` attr.
    """
    return (
        _unreduce_model,
        (
            to_qualified_name(type(model)),
            model.json(**getattr(model, "__reduce_kwargs__", {})),
        ),
    )


def _unreduce_model(model_name, json):
    """Helper for restoring model after serialization"""
    model = from_qualified_name(model_name)
    return model.parse_raw(json)


@overload
def add_cloudpickle_reduction(__model_cls: Type[M]) -> Type[M]:
    ...


@overload
def add_cloudpickle_reduction(
    **kwargs: Any,
) -> Callable[[Type[M]], Type[M]]:
    ...


def add_cloudpickle_reduction(__model_cls: Type[M] = None, **kwargs: Any):
    """
    Adds a `__reducer__` to the given class that ensures it is cloudpickle compatible.

    Workaround for issues with cloudpickle when using cythonized pydantic which
    throws exceptions when attempting to pickle the class which has "compiled"
    validator methods dynamically attached to it.

    We cannot define this utility in the model class itself because the class is the
    type that contains unserializable methods.

    Any model using some features of Pydantic (e.g. `Path` validation) with a Cython
    compiled Pydantic installation may encounter pickling issues.

    See related issue at https://github.com/cloudpipe/cloudpickle/issues/408
    """
    if __model_cls:
        __model_cls.__reduce__ = _reduce_model
        __model_cls.__reduce_kwargs__ = kwargs
        return __model_cls
    else:
        return cast(
            Callable[[Type[M]], Type[M]],
            partial(
                add_cloudpickle_reduction,
                **kwargs,
            ),
        )


def get_class_fields_only(model: Type[pydantic.BaseModel]) -> set:
    """
    Gets all the field names defined on the model class but not any parent classes.
    Any fields that are on the parent but redefined on the subclass are included.
    """
    subclass_class_fields = set(model.__annotations__.keys())
    parent_class_fields = set()

    for base in model.__class__.__bases__:
        if issubclass(base, pydantic.BaseModel):
            parent_class_fields.update(base.__annotations__.keys())

    return (subclass_class_fields - parent_class_fields) | (
        subclass_class_fields & parent_class_fields
    )


def add_type_dispatch(model_cls: Type[M]) -> Type[M]:
    """
    Extend a Pydantic model to add a 'type' field that is used a discriminator field
    to dynamically determine the subtype that when deserializing models.

    This allows automatic resolution to subtypes of the decorated model.

    If a type field already exists, it should be a string literal field that has a
    constant value for each subclass. The default value of this field will be used as
    the dispatch key.

    If a type field does not exist, one will be added. In this case, the value of the
    field will be set to the value of the `__dispatch_key__`. The base class should
    define a `__dispatch_key__` class method that is used to determine the unique key
    for each subclass. Alternatively, each subclass can define the `__dispatch_key__`
    as a string literal.

    The base class must not define a 'type' field. If it is not desirable to add a field
    to the model and the dispatch key can be tracked separately, the lower level
    utilities in `prefect.utilities.dispatch` should be used directly.
    """
    if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
        return v2_add_type_dispatch(model_cls)
    else:
        return v1_add_type_dispatch(model_cls)


class PartialModel(Generic[M]):
    """
    A utility for creating a Pydantic model in several steps.

    Fields may be set at initialization, via attribute assignment, or at finalization
    when the concrete model is returned.

    Pydantic validation does not occur until finalization.

    Each field can only be set once and a `ValueError` will be raised on assignment if
    a field already has a value.

    Example:
        >>> class MyModel(pydantic.BaseModel):
        >>>     x: int
        >>>     y: str
        >>>     z: float
        >>>
        >>> partial_model = PartialModel(MyModel, x=1)
        >>> partial_model.y = "two"
        >>> model = partial_model.finalize(z=3.0)
    """

    def __init__(self, __model_cls: Type[M], **kwargs: Any) -> None:
        self.fields = kwargs
        # Set fields first to avoid issues if `fields` is also set on the `model_cls`
        # in our custom `setattr` implementation.
        self.model_cls = __model_cls

        for name in kwargs.keys():
            self.raise_if_not_in_model(name)

    def finalize(self, **kwargs: Any) -> M:
        for name in kwargs.keys():
            self.raise_if_already_set(name)
            self.raise_if_not_in_model(name)
        return self.model_cls(**self.fields, **kwargs)

    def raise_if_already_set(self, name):
        if name in self.fields:
            raise ValueError(f"Field {name!r} has already been set.")

    def raise_if_not_in_model(self, name):
        if name not in self.model_cls.__fields__:
            raise ValueError(f"Field {name!r} is not present in the model.")

    def __setattr__(self, __name: str, __value: Any) -> None:
        if __name in {"fields", "model_cls"}:
            return super().__setattr__(__name, __value)

        self.raise_if_already_set(__name)
        self.raise_if_not_in_model(__name)
        self.fields[__name] = __value

    def __repr__(self) -> str:
        dsp_fields = ", ".join(
            f"{key}={repr(value)}" for key, value in self.fields.items()
        )
        return f"PartialModel(cls={self.model_cls.__name__}, {dsp_fields})"


class JsonPatch(JsonPatchBase):
    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(
            {
                "type": "array",
                "format": "rfc6902",
                "items": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
            }
        )
