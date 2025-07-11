from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Optional

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config

from ._defaults import default_local_storage_path


class ResultsSettings(PrefectBaseSettings):
    """
    Settings for controlling result storage behavior
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(("results",))

    default_serializer: str = Field(
        default="pickle",
        description="The default serializer to use when not otherwise specified.",
    )

    persist_by_default: bool = Field(
        default=False,
        description="The default setting for persisting results when not otherwise specified.",
    )

    default_storage_block: Optional[str] = Field(
        default=None,
        description="The `block-type/block-document` slug of a block to use as the default result storage.",
        validation_alias=AliasChoices(
            AliasPath("default_storage_block"),
            "prefect_results_default_storage_block",
            "prefect_default_result_storage_block",
        ),
    )

    local_storage_path: Path = Field(
        default_factory=default_local_storage_path,
        description="The default location for locally persisted results. Defaults to $PREFECT_HOME/storage.",
        validation_alias=AliasChoices(
            AliasPath("local_storage_path"),
            "prefect_results_local_storage_path",
            "prefect_local_storage_path",
        ),
    )
