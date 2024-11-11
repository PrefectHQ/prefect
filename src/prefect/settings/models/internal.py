from pydantic import AliasChoices, AliasPath, Field

from prefect.settings.base import PrefectBaseSettings, _build_settings_config
from prefect.types import LogLevel


class InternalSettings(PrefectBaseSettings):
    model_config = _build_settings_config(("internal",))

    logging_level: LogLevel = Field(
        default="ERROR",
        description="The default logging level for Prefect's internal machinery loggers.",
        validation_alias=AliasChoices(
            AliasPath("logging_level"),
            "prefect_internal_logging_level",
            "prefect_logging_internal_level",
        ),
    )
