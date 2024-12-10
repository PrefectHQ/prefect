from pydantic import AliasChoices, AliasPath, Field

from prefect.settings.base import PrefectBaseSettings, _build_settings_config


class ExperimentsSettings(PrefectBaseSettings):
    """
    Settings for configuring experimental features
    """

    model_config = _build_settings_config(("experiments",))

    warn: bool = Field(
        default=True,
        description="If `True`, warn on usage of experimental features.",
        validation_alias=AliasChoices(
            AliasPath("warn"), "prefect_experiments_warn", "prefect_experimental_warn"
        ),
    )

    telemetry_enabled: bool = Field(
        default=False,
        description="Enables sending telemetry to Prefect Cloud.",
    )

    lineage_events_enabled: bool = Field(
        default=False,
        description="If `True`, enables emitting lineage events. Set to `False` to disable lineage event emission.",
    )
