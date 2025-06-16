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
        from prefect.context import TaskAssetContext

        asset_ctx = TaskAssetContext.get()
        if asset_ctx:
            asset_ctx.add_asset_metadata(self.key, metadata)

    def materialize(self) -> None:
        from prefect.context import TaskAssetContext

        asset_ctx = TaskAssetContext.get()
        if asset_ctx:
            asset_ctx.add_downstream_asset(self)


def add_asset_metadata(asset: str | Asset, metadata: dict[str, Any]) -> None:
    """Utility to support adding metadata for an asset key or asset object to the current materialization"""

    asset = asset if isinstance(asset, Asset) else Asset(key=asset)
    asset.add_metadata(metadata)


def materialize_asset(asset: str | Asset) -> None:
    """Utility to add an asset key or asset object to the downstream assets of the current materialization"""

    asset = asset if isinstance(asset, Asset) else Asset(key=asset)
    asset.materialize()
