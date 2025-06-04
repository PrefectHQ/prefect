from __future__ import annotations

import re
from typing import Any, ClassVar, Optional

from pydantic import ConfigDict, Field, field_validator

from prefect._internal.schemas.bases import PrefectBaseModel

URI_REGEX = re.compile(r"^[a-z0-9]+://")


class AssetProperties(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    name: Optional[str] = Field(
        default=None, description="Human readable name of the Asset."
    )
    url: Optional[str] = Field(
        default=None, description="Visitable url to view the Asset."
    )
    description: Optional[str] = Field(
        default=None, description="Description of the Asset."
    )
    owners: Optional[list[str]] = Field(
        default=None, description="Owners of the Asset."
    )

    def __hash__(self) -> int:
        return hash((self.name, self.url, self.description, tuple(self.owners)))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, AssetProperties):
            return False
        return (
            self.name == other.name
            and self.url == other.url
            and self.description == other.description
            and self.owners == other.owners
        )


class Asset(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    key: str = Field(
        description="The key of the asset in a URI like format.",
        examples=["s3://bucket/folder/data.csv", "postgres://dbtable"],
    )
    properties: Optional[AssetProperties] = Field(
        default=None,
        description="Properties of the asset. "
        "Setting this will overwrite properties of a known asset.",
    )

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

    def add_metadata(self, metadata: dict[str, Any]):
        from prefect.context import AssetContext

        asset_ctx = AssetContext.get()
        if not asset_ctx:
            raise RuntimeError(
                "Unable add Asset metadata when not inside of an AssetContext"
            )

        asset_ctx.add_asset_metadata(self.key, metadata)


def add_asset_metadata(asset_key: str, metadata: dict[str, Any]) -> None:
    from prefect.context import AssetContext

    asset_ctx = AssetContext.get()
    if not asset_ctx:
        raise RuntimeError(
            "Unable to call `add_asset_metadata` when not inside of an AssetContext"
        )

    asset_ctx.add_asset_metadata(asset_key, metadata)
