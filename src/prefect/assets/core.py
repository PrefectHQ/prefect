from __future__ import annotations

from typing import Any, ClassVar, Optional

from pydantic import ConfigDict, Field

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.types import URILike


class AssetProperties(PrefectBaseModel):
    """
    Metadata properties to configure on an Asset
    """

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


class Asset(PrefectBaseModel):
    """
    Assets are objects that represent materialized data,
    providing a way to track lineage and dependencies.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    key: URILike
    properties: Optional[AssetProperties] = Field(
        default=None,
        description="Properties of the asset. "
        "Setting this will overwrite properties of a known asset.",
    )

    def __repr__(self) -> str:
        return f"Asset(key={self.key!r})"

    def __hash__(self) -> int:
        return hash(self.key)

    def add_metadata(self, metadata: dict[str, Any]) -> None:
        from prefect.context import AssetContext

        asset_ctx = AssetContext.get()
        if not asset_ctx:
            raise RuntimeError(
                "Unable add Asset metadata when not inside of an AssetContext"
            )

        asset_ctx.add_asset_metadata(self.key, metadata)


def add_asset_metadata(asset: str | Asset, metadata: dict[str, Any]) -> None:
    from prefect.context import AssetContext

    asset_ctx = AssetContext.get()
    if not asset_ctx:
        raise RuntimeError(
            "Unable to call `add_asset_metadata` when not inside of an AssetContext"
        )

    asset_key = asset if isinstance(asset, str) else asset.key
    asset_ctx.add_asset_metadata(asset_key, metadata)
