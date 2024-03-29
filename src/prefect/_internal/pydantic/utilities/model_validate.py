import typing

from prefect._internal.pydantic._flags import USE_V2_MODELS

if typing.TYPE_CHECKING:
    from prefect._internal.pydantic._base_model import BaseModel

T = typing.TypeVar("T", bound="BaseModel")

if USE_V2_MODELS:

    def model_validate(  # type: ignore[no-redef]
        model_instance: typing.Type[T],
        obj: typing.Any,
        *,
        strict: typing.Optional[bool] = False,
        from_attributes: typing.Optional[bool] = False,
        context: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> T:
        return model_instance.model_validate(
            obj,
            strict=strict,
            from_attributes=from_attributes,
            context=context,
        )

else:

    def model_validate(
        model_instance: typing.Type[T],
        obj: typing.Any,
        *,
        strict: typing.Optional[bool] = False,
        from_attributes: typing.Optional[bool] = False,
        context: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> T:
        return getattr(model_instance, "parse_obj")(obj)


__all__ = ["model_validate"]
