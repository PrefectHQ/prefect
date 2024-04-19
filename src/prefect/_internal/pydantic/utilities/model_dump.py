import typing
import warnings as python_warnings

from pydantic_core import from_json
from typing_extensions import Self

from prefect._internal.pydantic._base_model import BaseModel
from prefect._internal.pydantic._flags import USE_V2_MODELS

if typing.TYPE_CHECKING:
    from prefect._internal.pydantic._types import IncEx

T = typing.TypeVar("T", bound="BaseModel")


def model_dump(  # type: ignore[no-redef]
    model_instance: "BaseModel",
    *,
    mode: typing.Union[typing.Literal["json", "python"], str] = "python",
    include: "IncEx" = None,
    exclude: "IncEx" = None,
    by_alias: bool = False,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
    round_trip: bool = False,
    warnings: bool = True,
) -> typing.Dict[str, typing.Any]:
    """
    Generate a dictionary representation of the model, optionally specifying which fields to include or exclude.

    Args:
        mode: The mode in which `to_python` should run.
            If mode is 'json', the output will only contain JSON serializable types.
            If mode is 'python', the output may contain non-JSON-serializable Python objects.
        include: A set of fields to include in the output.
        exclude: A set of fields to exclude from the output.
        context: Additional context to pass to the serializer.
        by_alias: Whether to use the field's alias in the dictionary key if defined.
        exclude_unset: Whether to exclude fields that have not been explicitly set.
        exclude_defaults: Whether to exclude fields that are set to their default value.
        exclude_none: Whether to exclude fields that have a value of `None`.
        round_trip: If True, dumped values should be valid as input for non-idempotent types such as Json[T].
        warnings: Whether to log warnings when invalid fields are encountered.
        serialize_as_any: Whether to serialize fields with duck-typing serialization behavior.

    Returns:
        A dictionary representation of the model.
    """
    if USE_V2_MODELS and hasattr(model_instance, "model_dump"):
        return model_instance.model_dump(
            mode=mode,
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
        if mode == "json":
            with python_warnings.catch_warnings():
                python_warnings.simplefilter("ignore")
                return from_json(
                    model_instance.json(
                        include=include,
                        exclude=exclude,
                        by_alias=by_alias,
                        exclude_unset=exclude_unset,
                        exclude_defaults=exclude_defaults,
                        exclude_none=exclude_none,
                    )
                )

        return getattr(model_instance, "dict")(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )


class ModelDumpMixin(BaseModel):
    def model_dump(
        self: "Self",
        *,
        mode: typing.Union[typing.Literal["json", "python"], str] = "python",
        include: "IncEx" = None,
        exclude: "IncEx" = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool = True,
    ) -> typing.Dict[str, typing.Any]:
        """
        Generate a dictionary representation of the model, optionally specifying which fields to include or exclude.

        Args:
            mode: The mode in which `to_python` should run.
                If mode is 'json', the output will only contain JSON serializable types.
                If mode is 'python', the output may contain non-JSON-serializable Python objects.
            include: A set of fields to include in the output.
            exclude: A set of fields to exclude from the output.
            context: Additional context to pass to the serializer.
            by_alias: Whether to use the field's alias in the dictionary key if defined.
            exclude_unset: Whether to exclude fields that have not been explicitly set.
            exclude_defaults: Whether to exclude fields that are set to their default value.
            exclude_none: Whether to exclude fields that have a value of `None`.
            round_trip: If True, dumped values should be valid as input for non-idempotent types such as Json[T].
            warnings: Whether to log warnings when invalid fields are encountered.
            serialize_as_any: Whether to serialize fields with duck-typing serialization behavior.

        Returns:
            A dictionary representation of the model.
        """
        return model_dump(
            self,
            mode=mode,
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
        )


__all__ = ["model_dump", "ModelDumpMixin"]
