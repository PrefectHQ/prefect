from typing import Optional

from pydantic import AliasChoices, AliasPath, Field

from prefect.settings.base import PrefectBaseSettings, PrefectSettingsConfigDict


class ServerUISettings(PrefectBaseSettings):
    model_config = PrefectSettingsConfigDict(
        env_prefix="PREFECT_SERVER_UI_",
        env_file=".env",
        extra="ignore",
        toml_file="prefect.toml",
        prefect_toml_table_header=("server", "ui"),
    )

    enabled: bool = Field(
        default=True,
        description="Whether or not to serve the Prefect UI.",
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_server_ui_enabled",
            "prefect_ui_enabled",
        ),
    )

    api_url: Optional[str] = Field(
        default=None,
        description="The connection url for communication from the UI to the API. Defaults to `PREFECT_API_URL` if set. Otherwise, the default URL is generated from `PREFECT_SERVER_API_HOST` and `PREFECT_SERVER_API_PORT`.",
        validation_alias=AliasChoices(
            AliasPath("api_url"),
            "prefect_server_ui_api_url",
            "prefect_ui_api_url",
        ),
    )

    serve_base: str = Field(
        default="/",
        description="The base URL path to serve the Prefect UI from.",
        validation_alias=AliasChoices(
            AliasPath("serve_base"),
            "prefect_server_ui_serve_base",
            "prefect_ui_serve_base",
        ),
    )

    static_directory: Optional[str] = Field(
        default=None,
        description="The directory to serve static files from. This should be used when running into permissions issues when attempting to serve the UI from the default directory (for example when running in a Docker container).",
        validation_alias=AliasChoices(
            AliasPath("static_directory"),
            "prefect_server_ui_static_directory",
            "prefect_ui_static_directory",
        ),
    )
