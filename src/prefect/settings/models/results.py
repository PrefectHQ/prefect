from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, AliasPath, Field

from prefect.settings.base import PrefectBaseSettings, _build_settings_config


class ResultsSettings(PrefectBaseSettings):
    """
    Settings for controlling result storage behavior
    """

    model_config = _build_settings_config(("results",))

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

    local_storage_path: Optional[Path] = Field(
        default=None,
        description="The path to a directory to store results in.",
        validation_alias=AliasChoices(
            AliasPath("local_storage_path"),
            "prefect_results_local_storage_path",
            "prefect_local_storage_path",
        ),
    )
