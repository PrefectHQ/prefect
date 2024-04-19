import typing

from prefect._internal.pydantic._base_model import BaseModel
from prefect._internal.pydantic._flags import USE_V2_MODELS


def model_fields_set(model_instance: "BaseModel") -> typing.Set[str]:
    """
    Returns a set of the model's fields.
    """
    if USE_V2_MODELS:
        return getattr(model_instance, "__pydantic_fields_set__")
    else:
        return getattr(model_instance, "__fields_set__")


class ModelFieldsSetMixin(BaseModel):
    @property
    def model_fields_set(self) -> typing.Set[str]:
        """Returns the set of fields that have been explicitly set on this model instance.

        Returns:
            A set of strings representing the fields that have been set,
                i.e. that were not filled from defaults.
        """
        return model_fields_set(self)


__all__ = ["ModelFieldsSetMixin", "model_fields_set"]
