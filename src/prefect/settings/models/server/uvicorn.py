from typing import Optional

from pydantic import Field

from prefect.settings.base import PrefectBaseSettings, PrefectSettingsConfigDict
from prefect.types import PositiveInteger


class ServerUvicornSettings(PrefectBaseSettings):
    model_config = PrefectSettingsConfigDict(
        env_file=".env",
        extra="ignore",
        toml_file="prefect.toml",
        prefect_toml_table_header=("server", "uvicorn"),
        env_prefix="PREFECT_SERVER_UVICORN_",
    )

    workers: Optional[PositiveInteger] = Field(
        default=None, description="The number of worker processes for the API server."
    )
