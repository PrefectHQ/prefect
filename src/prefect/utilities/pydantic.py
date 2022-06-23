from typing import Any, Type, TypeVar

import pydantic
from typing_extensions import Self

from prefect.utilities.importtools import from_qualified_name, to_qualified_name

D = TypeVar("D", bound=Any)
M = TypeVar("M", bound=Type[pydantic.BaseModel])


def add_type_dispatch(model_cls: M) -> M:
    """
    Extend a Pydantic model to add a field that includes the import path for the model
    on serialization and dynamically imports the model on deserialization. This allows
    automatic resolution to subtypes of the decorated model.
    """
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
        data.setdefault("type", to_qualified_name(__pydantic_self__.__class__))
        cls_init(__pydantic_self__, **data)

    def __new__(cls: Type[Self], **kwargs) -> Self:
        if "type" in kwargs:
            subcls = from_qualified_name(kwargs["type"])
            return cls_new(subcls)
        else:
            return cls_new(cls)

    model_cls.__init__ = __init__
    model_cls.__new__ = __new__

    return model_cls
