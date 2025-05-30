from __future__ import annotations

import re
from typing import TypeVar

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
        return f"Asset(key={self.key!r})"

    def __hash__(self) -> int:
        return hash(self.key)
