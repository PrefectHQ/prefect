from pydantic import AliasChoices, AliasPath, Field

from prefect.settings.base import PrefectBaseSettings, PrefectSettingsConfigDict
from prefect.types import LogLevel


class InternalSettings(PrefectBaseSettings):
    model_config = PrefectSettingsConfigDict(
        env_prefix="PREFECT_INTERNAL_",
        env_file=".env",
        extra="ignore",
        toml_file="prefect.toml",
        prefect_toml_table_header=("internal",),
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
