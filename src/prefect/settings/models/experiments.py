from pydantic import Field

from prefect.settings.base import PrefectBaseSettings, _build_settings_config


class ExperimentsSettings(PrefectBaseSettings):
    """
    Settings for configuring experimental features
    """

    model_config = _build_settings_config(("experiments",))

    worker_logging_to_api_enabled: bool = Field(
        default=False,
        description="Enables the logging of worker logs to Prefect Cloud.",
    )
