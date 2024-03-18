from typing import Any, Dict, Literal, Set, Union

import typing_extensions
from pydantic import BaseModel

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS

IncEx: typing_extensions.TypeAlias = (
    "Union[Set[int], Set[str], Dict[int, Any], Dict[str, Any], None]"
)


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
    if HAS_PYDANTIC_V2:
        if PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS:
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
            return model_instance.dict(
                include=include,
                exclude=exclude,
                by_alias=by_alias,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
            )
    else:
        return model_instance.dict(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )
