from pydantic import Field

from prefect.settings.base import PrefectBaseSettings, PrefectSettingsConfigDict


class ExperimentsSettings(PrefectBaseSettings):
    """
    Settings for configuring experimental features
    """

    model_config = PrefectSettingsConfigDict(
        env_prefix="PREFECT_EXPERIMENTS_",
        env_file=".env",
        extra="ignore",
        toml_file="prefect.toml",
        prefect_toml_table_header=("experiments",),
    )

    worker_logging_to_api_enabled: bool = Field(
        default=False,
        description="Enables the logging of worker logs to Prefect Cloud.",
    )
