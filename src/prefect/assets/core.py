from __future__ import annotations

import re
from typing import ClassVar

from pydantic import ConfigDict, field_validator

from prefect._internal.schemas.bases import PrefectBaseModel

URI_REGEX = re.compile(r"^[a-z0-9]+://")


class Asset(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    key: str

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
