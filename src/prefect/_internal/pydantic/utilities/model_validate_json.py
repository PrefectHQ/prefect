import typing

from prefect._internal.pydantic._flags import USE_V2_MODELS

if typing.TYPE_CHECKING:
    from prefect._internal.pydantic._base_model import BaseModel

T = typing.TypeVar("T", bound="BaseModel")

if USE_V2_MODELS:

    def model_validate_json(  # type: ignore[no-redef]
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
        return model.model_validate_json(
            json_data,
            strict=strict,
            context=context,
        )

else:

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
        return getattr(model, "parse_raw")(json_data)


__all__ = ["model_validate_json"]
