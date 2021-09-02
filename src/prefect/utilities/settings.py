"""Settings for Prefect and Prefect Orion

Note that when implementing nested settings, a `default_factory` should be used
to avoid instantiating the nested settings class until runtime.
"""
from pathlib import Path

from pydantic import BaseSettings, Field, SecretStr


class DataLocationSettings(BaseSettings):
    class Config:
        env_prefix = "PREFECT_ORION_DATA_"
        frozen = True

    name: str = "default"
    scheme: str = "file"
    base_path: str = "/tmp"


class DatabaseSettings(BaseSettings):
    class Config:
        env_prefix = "PREFECT_ORION_DATABASE_"
        frozen = True

    # the default connection_url is an in-memory sqlite database
    # that can be accessed from multiple threads
    connection_url: SecretStr = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true&check_same_thread=false"
    echo: bool = False

    # a default limit for queries
    default_limit: int = 200


class OrionSettings(BaseSettings):
    class Config:
        env_prefix = "PREFECT_ORION_"
        frozen = True

    # database
    # using `default_factory` avoids instantiating the default value until the parent
    # settings class is instantiated
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)

    data: DataLocationSettings = Field(default_factory=DataLocationSettings)


class LoggingSettings(BaseSettings):
    class Config:
        env_prefix = "PREFECT_LOGGING_"
        frozen = True

    settings_path: Path = Path("~/.prefect/logging.yml").expanduser()


class Settings(BaseSettings):
    class Config:
        env_prefix = "PREFECT_"
        frozen = True

    # debug
    debug_mode: bool = False
    test_mode: bool = False

    # logging
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    # orion
    orion: OrionSettings = Field(default_factory=OrionSettings)

    # the connection url for an orion instance
    orion_host: str = None


settings = Settings()
