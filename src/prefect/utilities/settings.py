"""Settings for Prefect and Prefect Orion

Note that when implementing nested settings, a `default_factory` should be used
to avoid instantiating the nested settings class until runtime.
"""
from pathlib import Path
from datetime import timedelta
from pydantic import BaseSettings, Field, SecretStr
from typing import Optional, Any, Dict


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

    # statement timeout, in seconds
    timeout: Optional[float] = 1
    # statement timeout for services, in seconds
    services_timeout: Optional[float] = None


class APISettings(BaseSettings):

    # a default limit for queries
    default_limit: int = 200


class ServicesSettings(BaseSettings):
    class Config:
        env_prefix = "PREFECT_ORION_SERVICES_"
        frozen = True

    # run scheduler every 60 seconds
    scheduler_loop_seconds: float = 60
    # batch deployments in groups of 100
    scheduler_deployment_batch_size: int = 100
    # schedule up to 100 new runs per deployment
    scheduler_max_runs: int = 100
    # schedule at most three months into the future
    scheduler_max_future_seconds: int = timedelta(days=100).total_seconds()


class OrionSettings(BaseSettings):
    class Config:
        env_prefix = "PREFECT_ORION_"
        frozen = True

    # database
    # using `default_factory` avoids instantiating the default value until the parent
    # settings class is instantiated
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)

    data: DataLocationSettings = Field(default_factory=DataLocationSettings)
    api: APISettings = Field(default_factory=APISettings)
    services: ServicesSettings = Field(default_factory=ServicesSettings)


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


class NotSetType:
    def __eq__(self, o: object) -> bool:
        return isinstance(o, NotSetType)


NOTSET = NotSetType()


def drop_unset(**kwargs: Any) -> Dict[str, Any]:
    return {key: value for key, value in kwargs.items() if value != NOTSET}
