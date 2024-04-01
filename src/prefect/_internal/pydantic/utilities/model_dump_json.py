import typing

from typing_extensions import Self

from prefect._internal.pydantic._base_model import BaseModel
from prefect._internal.pydantic._flags import USE_V2_MODELS

if typing.TYPE_CHECKING:
    from prefect._internal.pydantic._types import IncEx

T = typing.TypeVar("T", bound="BaseModel")


def model_dump_json(
    model_instance: "BaseModel",
    *,
    indent: typing.Optional[int] = None,
    include: "IncEx" = None,
    exclude: "IncEx" = None,
    by_alias: bool = False,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
    round_trip: bool = False,
    warnings: bool = True,
) -> str:
    """
    Generate a JSON representation of the model, optionally specifying which fields to include or exclude.

    Args:
        indent: If provided, the number of spaces to indent the JSON output.
        include: A list of fields to include in the output.
        exclude: A list of fields to exclude from the output.
        by_alias: Whether to use the field's alias in the dictionary key if defined.
        exclude_unset: Whether to exclude fields that have not been explicitly set.
        exclude_defaults: Whether to exclude fields that are set to their default value.
        exclude_none: Whether to exclude fields that have a value of `None`.
        round_trip: If True, dumped values should be valid as input for non-idempotent types such as Json[T].
        warnings: Whether to log warnings when invalid fields are encountered.

    Returns:
        A JSON representation of the model.
    """
    if USE_V2_MODELS:
        return model_instance.model_dump_json(
            indent=indent,
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
        )
    else:
        return getattr(model_instance, "json")(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )


class ModelDumpJsonMixin(BaseModel):
    def model_dump_json(
        self: "Self",
        *,
        indent: typing.Optional[int] = None,
        include: "IncEx" = None,
        exclude: "IncEx" = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool = True,
    ) -> str:
        """
        Generate a JSON representation of the model, optionally specifying which fields to include or exclude.

        Args:
            indent: If provided, the number of spaces to indent the JSON output.
            include: A list of fields to include in the output.
            exclude: A list of fields to exclude from the output.
            by_alias: Whether to use the field's alias in the dictionary key if defined.
            exclude_unset: Whether to exclude fields that have not been explicitly set.
            exclude_defaults: Whether to exclude fields that are set to their default value.
            exclude_none: Whether to exclude fields that have a value of `None`.
            round_trip: If True, dumped values should be valid as input for non-idempotent types such as Json[T].
            warnings: Whether to log warnings when invalid fields are encountered.

        Returns:
            A JSON representation of the model.
        """
        return model_dump_json(
            self,
            indent=indent,
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
        )


__all__ = ["model_dump_json", "ModelDumpJsonMixin"]
