import typing

from prefect._internal.pydantic._flags import USE_V2_MODELS

if typing.TYPE_CHECKING:
    from prefect._internal.pydantic._base_model import BaseModel

T = typing.TypeVar("T", bound="BaseModel")

if USE_V2_MODELS:

    def model_construct(  # type: ignore[no-redef]
        model_instance: typing.Type[T],
        _fields_set: typing.Optional[typing.Set[str]] = None,
        **values: typing.Any,
    ) -> T:
        return model_instance.model_construct(_fields_set=_fields_set, **values)

else:

    def model_construct(
        model_instance: typing.Type[T],
        _fields_set: typing.Optional[typing.Set[str]] = None,
        **values: typing.Any,
    ) -> T:
        return getattr(model_instance, "construct")(**values)


__all__ = ["model_construct"]
