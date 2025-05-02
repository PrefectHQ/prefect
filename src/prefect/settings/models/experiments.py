from __future__ import annotations

from typing import ClassVar

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class ExperimentsSettings(PrefectBaseSettings):
    """
    Settings for configuring experimental features
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(("experiments",))

    warn: bool = Field(
        default=True,
        description="If `True`, warn on usage of experimental features.",
        validation_alias=AliasChoices(
            AliasPath("warn"), "prefect_experiments_warn", "prefect_experimental_warn"
        ),
    )

    lineage_events_enabled: bool = Field(
        default=False,
        description="If `True`, enables emitting lineage events. Set to `False` to disable lineage event emission.",
    )
