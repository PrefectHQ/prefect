from typing import Any, Type, TypeVar

from typing_extensions import Self

from prefect._internal.pydantic._flags import HAS_PYDANTIC_V2, USE_PYDANTIC_V2

if HAS_PYDANTIC_V2 and not USE_PYDANTIC_V2:
    import pydantic.v1 as pydantic
else:
    import pydantic

from prefect.utilities.dispatch import get_dispatch_key, lookup_type, register_base_type

M = TypeVar("M", bound=pydantic.BaseModel)


def v1_add_type_dispatch(model_cls: Type[M]) -> Type[M]:
    defines_dispatch_key = hasattr(
        model_cls, "__dispatch_key__"
    ) or "__dispatch_key__" in getattr(model_cls, "__annotations__", {})

    defines_type_field = "type" in model_cls.__fields__

    if not defines_dispatch_key and not defines_type_field:
        raise ValueError(
            f"Model class {model_cls.__name__!r} does not define a `__dispatch_key__` "
            "or a type field. One of these is required for dispatch."
        )

    elif defines_dispatch_key and not defines_type_field:
        # Add a type field to store the value of the dispatch key
        model_cls.__fields__["type"] = pydantic.fields.ModelField(
            name="type",
            type_=str,
            required=True,
            class_validators=None,
            model_config=model_cls.__config__,
        )

    elif not defines_dispatch_key and defines_type_field:
        field_type_annotation = model_cls.__fields__["type"].type_
        if field_type_annotation != str:
            raise TypeError(
                f"Model class {model_cls.__name__!r} defines a 'type' field with "
                f"type {field_type_annotation.__name__!r} but it must be 'str'."
            )

        # Set the dispatch key to retrieve the value from the type field
        @classmethod
        def dispatch_key_from_type_field(cls):
            return cls.__fields__["type"].default

        model_cls.__dispatch_key__ = dispatch_key_from_type_field

    else:
        raise ValueError(
            f"Model class {model_cls.__name__!r} defines a `__dispatch_key__` "
            "and a type field. Only one of these may be defined for dispatch."
        )

    cls_init = model_cls.__init__
    cls_new = model_cls.__new__

    def __init__(__pydantic_self__, **data: Any) -> None:
        type_string = (
            get_dispatch_key(__pydantic_self__)
            if type(__pydantic_self__) != model_cls
            else "__base__"
        )
        data.setdefault("type", type_string)
        cls_init(__pydantic_self__, **data)

    def __new__(cls: Type[Self], **kwargs) -> Self:
        if "type" in kwargs:
            try:
                subcls = lookup_type(cls, dispatch_key=kwargs["type"])
            except KeyError as exc:
                raise pydantic.ValidationError(errors=[exc], model=cls)
            return cls_new(subcls)
        else:
            return cls_new(cls)

    model_cls.__init__ = __init__
    model_cls.__new__ = __new__

    register_base_type(model_cls)

    return model_cls


def v2_add_type_dispatch(model_cls: Type[M]) -> Type[M]:
    # TODO: Implement this
    return model_cls
