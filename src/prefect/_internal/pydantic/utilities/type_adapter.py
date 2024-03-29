import typing

from prefect._internal.pydantic._flags import USE_V2_MODELS

T = typing.TypeVar("T")

if USE_V2_MODELS:
    from pydantic import TypeAdapter  # type: ignore[no-redef]

else:
    from pydantic import parse_obj_as  # type: ignore[no-redef]

    class TypeAdapter(typing.Generic[T]):
        def __init__(self, type_: typing.Union[T, typing.Type[T]]) -> None:
            self.type_ = type_

        def validate_python(
            self,
            __object: typing.Any,
            /,
            *,
            strict: typing.Optional[bool] = None,
            from_attributes: typing.Optional[bool] = None,
            context: typing.Optional[typing.Dict[str, typing.Any]] = None,
        ) -> T:
            return parse_obj_as(self.type_, __object)  # type: ignore


def validate_python(
    type_: typing.Union[T, typing.Type[T]],
    __object: typing.Any,
    /,
    *,
    strict: typing.Optional[bool] = None,
    from_attributes: typing.Optional[bool] = None,
    context: typing.Optional[typing.Dict[str, typing.Any]] = None,
) -> T:
    """Validate a Python object against the model.

    Args:
        type_: The type to validate against.
        __object: The Python object to validate against the model.
        strict: Whether to strictly check types.
        from_attributes: Whether to extract data from object attributes.
        context: Additional context to pass to the validator.

    !!! note
        When using `TypeAdapter` with a Pydantic `dataclass`, the use of the `from_attributes`
        argument is not supported.

    Returns:
        The validated object.
    """
    return TypeAdapter(type_).validate_python(__object)


__all__ = ["TypeAdapter"]
