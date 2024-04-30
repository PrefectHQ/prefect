import typing

from typing_extensions import Self

from prefect._internal.pydantic._base_model import BaseModel
from prefect._internal.pydantic._flags import USE_V2_MODELS

T = typing.TypeVar("T", bound="BaseModel")


def model_validate_json(
    model: typing.Type[T],
    json_data: typing.Union[str, bytes, bytearray],
    *,
    strict: typing.Optional[bool] = False,
    context: typing.Optional[typing.Dict[str, typing.Any]] = None,
) -> T:
    """
    Validate the given JSON data against the Pydantic model.

    Args:
        json_data: The JSON data to validate.
        strict: Whether to enforce types strictly.
        context: Extra variables to pass to the validator.

    Returns:
        The validated Pydantic model.

    Raises:
        ValueError: If `json_data` is not a JSON string.
    """
    if USE_V2_MODELS:
        return model.model_validate_json(
            json_data,
            strict=strict,
            context=context,
        )
    else:
        return getattr(model, "parse_raw")(json_data)


class ModelValidateJsonMixin(BaseModel):
    @classmethod
    def model_validate_json(
        cls: typing.Type["Self"],
        json_data: typing.Union[str, bytes, bytearray],
        *,
        strict: typing.Optional[bool] = False,
        context: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> "Self":
        """
        Validate the given JSON data against the Pydantic model.

        Args:
            json_data: The JSON data to validate.
            strict: Whether to enforce types strictly.
            context: Extra variables to pass to the validator.

        Returns:
            The validated Pydantic model.

        Raises:
            ValueError: If `json_data` is not a JSON string.
        """
        return model_validate_json(cls, json_data, strict=strict, context=context)


__all__ = ["model_validate_json", "ModelValidateJsonMixin"]
