from typing import Any, Dict, Literal, Set, Union

import typing_extensions
from pydantic import BaseModel

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.logging.loggers import get_logger
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS

IncEx: typing_extensions.TypeAlias = (
    "Union[Set[int], Set[str], Dict[int, Any], Dict[str, Any], None]"
)

logger = get_logger("prefect._internal.pydantic")


def model_dump(
    model_instance: BaseModel,
    *,
    mode: Union[Literal["json", "python"], str] = "python",
    include: IncEx = None,
    exclude: IncEx = None,
    by_alias: bool = False,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
    round_trip: bool = False,
    warnings: bool = True,
) -> Dict[str, Any]:
    if not isinstance(model_instance, BaseModel):
        raise TypeError(
            f"Expected a Pydantic model, but got {type(model_instance).__name__}"
        )

    should_dump_as_v2_model = (
        HAS_PYDANTIC_V2 and PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS
    )

    if should_dump_as_v2_model:
        logger.debug(
            "Using Pydantic v2 compatibility layer for `model_dump`. This will be removed in a future release."
        )
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
        if HAS_PYDANTIC_V2:
            logger.debug(
                "Pydantic v2 compatibility layer is disabled. To enable, set `PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS` to `True`."
            )
        else:
            logger.debug("Pydantic v2 is not installed.")

        return model_instance.dict(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )
