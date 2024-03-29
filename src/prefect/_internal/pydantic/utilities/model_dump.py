import typing

from prefect._internal.pydantic._flags import USE_V2_MODELS

if typing.TYPE_CHECKING:
    from prefect._internal.pydantic._base_model import BaseModel
    from prefect._internal.pydantic._types import IncEx

T = typing.TypeVar("T", bound="BaseModel")

if USE_V2_MODELS:

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

    def model_dump(
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
    ) -> "BaseModel":
        return getattr(model_instance, "dict")(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )


__all__ = ["model_dump"]
