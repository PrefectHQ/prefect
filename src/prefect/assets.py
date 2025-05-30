from __future__ import annotations

import re
from typing import Any, Callable, Optional, TypeVar, Union

from pydantic import ConfigDict, field_validator
from typing_extensions import ParamSpec

from prefect._internal.schemas.bases import PrefectBaseModel

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")


URI_REGEX = re.compile(r"^[a-z0-9]+://")


class Asset(PrefectBaseModel):
    key: str

    model_config = ConfigDict(frozen=True)

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if not URI_REGEX.match(value):
            raise ValueError(
                "Key must be a valid URI, e.g. storage://bucket/folder/asset.csv"
            )
        return value

    def __repr__(self) -> str:
        return f"Asset(key={self.key!r}, name={self.name!r})"

    def __hash__(self) -> int:
        return hash(self.key)


# TODO FIX TYPING HERE
def materialize(
    *assets: Union[str, Asset],
    asset_deps: Optional[list[Union[str, Asset]]] = None,
    **task_kwargs: Any,
):  # -> Callable[[Callable[P, R]], Task[P, R]]:
    """
    Decorator for materializing assets.

    Args:
        *assets: Assets to materialize
        asset_deps: Additional upstream assets to observe
        **task_kwargs: Additional task configuration
    """
    if not assets:
        raise TypeError(
            "materialize requires at least one asset argument, e.g. `@materialize(asset1)`"
        )

    asset_objs = [Asset(key=a) if isinstance(a, str) else a for a in assets]

    # TODO FIX TYPING
    def decorator(fn: Callable[P, R]):  # -> Task[P, R]
        from prefect import Task

        task = Task(fn=fn, asset_deps=asset_deps, **task_kwargs)
        task.assets = asset_objs
        return task

    return decorator
