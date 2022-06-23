from typing import Any, Dict, Generic, Type, TypeVar

import pydantic
from typing_extensions import Self

from prefect.utilities.importtools import from_qualified_name, to_qualified_name

D = TypeVar("D", bound=Any)
M = TypeVar("M", bound=pydantic.BaseModel)

TYPE_REGISTRY: Dict[Type[pydantic.BaseModel], Dict[str, Type[pydantic.BaseModel]]] = {}


def get_registry_for_type(cls: Type[M]) -> Dict[str, Type[M]]:
    """
    Get the first matching registry for a class or any of its base classes.

    If not found, an empty dictionary is returned.
    """
    return next(filter(None, (TYPE_REGISTRY.get(cls) for cls in cls.mro())), {})


def add_type_dispatch(model_cls: Type[M]) -> Type[M]:
    """
    Extend a Pydantic model to add a field that includes the import path for the model
    on serialization and dynamically imports the model on deserialization. This allows
    automatic resolution to subtypes of the decorated model.
    """
    if "__typename__" in getattr(model_cls, "__annotations__", {}):
        TYPE_REGISTRY[model_cls] = {}

    if "type" in model_cls.__fields__:
        raise ValueError(
            f"Model class {model_cls.__name__!r} includes reserved field 'type' used "
            "for dispatch."
        )
    else:
        model_cls.__fields__["type"] = pydantic.fields.ModelField(
            name="type",
            type_=str,
            required=True,
            class_validators=None,
            model_config=model_cls.__config__,
        )

    cls_init = model_cls.__init__
    cls_new = model_cls.__new__

    def __init__(__pydantic_self__, **data: Any) -> None:
        data.setdefault(
            "type",
            __pydantic_self__.__typename__
            if hasattr(__pydantic_self__, "__typename__")
            else to_qualified_name(__pydantic_self__.__class__),
        )
        cls_init(__pydantic_self__, **data)

    def __new__(cls: Type[Self], **kwargs) -> Self:
        if "type" in kwargs:
            # Get the first matching registry for this class or one of its bases
            registry = get_registry_for_type(cls)
            registry_cls = registry.get(kwargs["type"])

            # If no registry was found, attempt to import the name
            subcls = registry_cls or from_qualified_name(kwargs["type"])

            # Check that we got a valid subclass, in-case we
            if not isinstance(subcls, type):
                raise ValueError(
                    f"Found invalid object {subcls!r}: expected 'type' object."
                )
            if not issubclass(subcls, cls):
                raise ValueError(
                    f"Found invalid class {subcls!r}: not a subclass of {cls!r}."
                )

            return cls_new(subcls)
        else:
            return cls_new(cls)

    model_cls.__init__ = __init__
    model_cls.__new__ = __new__

    return model_cls


def register_dispatch_type(model_cls: Type[M]) -> Type[M]:
    # Validate the model type

    base = model_cls.__base__
    if base not in TYPE_REGISTRY:
        raise KeyError(
            f"Base type {base.__name__!r} for model {model_cls.__name__!r} not found "
            "in registry."
        )

    if not getattr(model_cls, "__typename__", None):
        raise ValueError(
            f"Model {model_cls.__name__!r} does not define a value for "
            "'__typename__' which is requried for registry lookup."
        )

    # Add to the registry
    TYPE_REGISTRY[base][model_cls.__typename__] = model_cls

    return model_cls


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
        dsp_fields = ", ".join(f"{key}={repr(value)}" for key, value in self.fields)
        return f"PartialModel({self.model_cls.__name__}{dsp_fields})"
