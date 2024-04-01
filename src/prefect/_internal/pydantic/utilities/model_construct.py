import typing

from typing_extensions import Self

from prefect._internal.pydantic._base_model import BaseModel
from prefect._internal.pydantic._flags import USE_V2_MODELS

T = typing.TypeVar("T", bound="BaseModel")


def model_construct(
    model: typing.Type[T],
    _fields_set: typing.Optional[typing.Set[str]] = None,
    **values: typing.Any,
) -> T:
    """Creates a new instance of the `model` class with validated data.

    Creates a new model setting `__dict__` and `__pydantic_fields_set__` from trusted or pre-validated data.
    Default values are respected, but no other validation is performed.

    Args:
        _fields_set: The set of field names accepted for the Model instance.
        values: Trusted or pre-validated data dictionary.

    Returns:
        A new instance of the `model` class with validated data.
    """
    if USE_V2_MODELS:
        return model.model_construct(_fields_set=_fields_set, **values)
    else:
        return getattr(model, "construct")(**values)


class ModelConstructMixin(BaseModel):
    @classmethod
    def model_construct(
        cls: typing.Type["Self"],
        _fields_set: typing.Optional[typing.Set[str]] = None,
        **values: typing.Any,
    ) -> "Self":
        """Creates a new instance of the `model` class with validated data.

        Creates a new model setting `__dict__` and `__pydantic_fields_set__` from trusted or pre-validated data.
        Default values are respected, but no other validation is performed.

        Args:
            _fields_set: The set of field names accepted for the Model instance.
            values: Trusted or pre-validated data dictionary.

        Returns:
            A new instance of the `model` class with validated data.
        """
        return model_construct(cls, _fields_set=_fields_set, **values)


__all__ = ["model_construct", "ModelConstructMixin"]
