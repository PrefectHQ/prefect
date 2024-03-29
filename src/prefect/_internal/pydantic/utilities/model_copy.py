import typing

from prefect._internal.pydantic._flags import USE_V2_MODELS

if typing.TYPE_CHECKING:
    from prefect._internal.pydantic._base_model import BaseModel

T = typing.TypeVar("T", bound="BaseModel")

if USE_V2_MODELS:

    def model_copy(  # type: ignore[no-redef]
        model_instance: T,
        *,
        update: typing.Optional[typing.Dict[str, typing.Any]] = None,
        deep: bool = False,
    ) -> T:
        """
        Returns a copy of the model.

        Args:
            update: Values to change/add in the new model. Note: the data is not validated
                before creating the new model. You should trust this data.
            deep: Set to `True` to make a deep copy of the model.

        Returns:
            New model instance.
        """
        return model_instance.model_copy(update=update, deep=deep)

else:

    def model_copy(
        model_instance: "BaseModel",
        *,
        update: typing.Optional[typing.Dict[str, typing.Any]] = None,
        deep: bool = False,
    ) -> "BaseModel":
        """
        Returns a copy of the model.

        Args:
            update: Values to change/add in the new model. Note: the data is not validated
                before creating the new model. You should trust this data.
            deep: Set to `True` to make a deep copy of the model.

        Returns:
            New model instance.
        """
        return getattr(model_instance, "copy")(update=update, deep=deep)


__all__ = ["model_copy"]
