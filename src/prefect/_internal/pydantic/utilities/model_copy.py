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
        return model_instance.model_copy(update=update, deep=deep)

else:

    def model_copy(
        model_instance: "BaseModel",
        *,
        update: typing.Optional[typing.Dict[str, typing.Any]] = None,
        deep: bool = False,
    ) -> "BaseModel":
        return getattr(model_instance, "copy")(update=update, deep=deep)


__all__ = ["model_copy"]
