import typing

from prefect._internal.pydantic._flags import USE_V2_MODELS

T = typing.TypeVar("T")

if USE_V2_MODELS:
    from pydantic import TypeAdapter  # type: ignore

else:
    from pydantic import parse_obj_as  # type: ignore

    class TypeAdapter(typing.Generic[T]):
        """
        Type adapters provide a flexible way to perform validation and serialization based on a Python type.

        A `TypeAdapter` instance exposes some of the functionality from `BaseModel` instance methods
        for types that do not have such methods (such as dataclasses, primitive types, and more).

        **Note:** `TypeAdapter` instances are not types, and cannot be used as type annotations for fields.

        Attributes:
            core_schema: The core schema for the type.
            validator (SchemaValidator): The schema validator for the type.
            serializer: The schema serializer for the type.
        """

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


__all__ = ["TypeAdapter", "validate_python"]
