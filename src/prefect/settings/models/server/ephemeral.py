from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings


class ServerEphemeralSettings(PrefectBaseSettings):
    """
    Settings for controlling ephemeral server behavior
    """

    model_config = SettingsConfigDict(
        env_prefix="PREFECT_SERVER_EPHEMERAL_", env_file=".env", extra="ignore"
    )

    enabled: bool = Field(
        default=False,
        description="""
        Controls whether or not a subprocess server can be started when no API URL is provided.
        """,
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_server_ephemeral_enabled",
            "prefect_server_allow_ephemeral_mode",
        ),
    )

    startup_timeout_seconds: int = Field(
        default=20,
        description="""
        The number of seconds to wait for the server to start when ephemeral mode is enabled.
        Defaults to `10`.
        """,
    )
