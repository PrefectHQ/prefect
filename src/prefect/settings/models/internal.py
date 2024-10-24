from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings
from prefect.types import LogLevel


class InternalSettings(PrefectBaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PREFECT_INTERNAL_", env_file=".env", extra="ignore"
    )

    logging_level: LogLevel = Field(
        default="ERROR",
        description="The default logging level for Prefect's internal machinery loggers.",
        validation_alias=AliasChoices(
            AliasPath("logging_level"),
            "prefect_internal_logging_level",
            "prefect_logging_internal_level",
        ),
    )
