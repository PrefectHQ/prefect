import typing

from typing_extensions import Self

from prefect._internal.pydantic._base_model import BaseModel
from prefect._internal.pydantic._flags import USE_V2_MODELS

T = typing.TypeVar("T", bound="BaseModel")


def model_validate(
    model_instance: typing.Type[T],
    obj: typing.Any,
    *,
    strict: typing.Optional[bool] = False,
    from_attributes: typing.Optional[bool] = False,
    context: typing.Optional[typing.Dict[str, typing.Any]] = None,
) -> T:
    """
    Validate a pydantic model instance.

    Args:
        obj: The object to validate.
        strict: Whether to enforce types strictly.
        from_attributes: Whether to extract data from object attributes.
        context: Additional context to pass to the validator.

    Raises:
        ValidationError: If the object could not be validated.

    Returns:
        The validated model instance.
    """
    if USE_V2_MODELS:
        return model_instance.model_validate(
            obj,
            strict=strict,
            from_attributes=from_attributes,
            context=context,
        )
    else:
        return getattr(model_instance, "parse_obj")(obj)


class ModelValidateMixin(BaseModel):
    @classmethod
    def model_validate(
        cls: typing.Type["Self"],
        obj: typing.Any,
        *,
        strict: typing.Optional[bool] = False,
        from_attributes: typing.Optional[bool] = False,
        context: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> "Self":
        """
        Validate a pydantic model instance.

        Args:
            obj: The object to validate.
            strict: Whether to enforce types strictly.
            from_attributes: Whether to extract data from object attributes.
            context: Additional context to pass to the validator.

        Raises:
            ValidationError: If the object could not be validated.

        Returns:
            The validated model instance.
        """
        return model_validate(
            cls, obj, strict=strict, from_attributes=from_attributes, context=context
        )


__all__ = ["model_validate"]
