"""Settings for Prefect and Prefect Orion

Note that when implementing nested settings, a `default_factory` should be used
to avoid instantiating the nested settings class until runtime.
"""
from pathlib import Path


from pydantic import BaseSettings, Field, SecretStr


class DatabaseSettings(BaseSettings):
    class Config:
        env_prefix = "PREFECT_ORION_DATABASE_"
        frozen = True

    connection_url: SecretStr = "sqlite+aiosqlite:///:memory:"
    echo: bool = False


class OrionSettings(BaseSettings):
    class Config:
        env_prefix = "PREFECT_ORION_"
        frozen = True

    # database
    # using `default_factory` avoids instantiating the default value until the parent
    # settings class is instantiated
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)


class LoggingSettings(BaseSettings):
    class Config:
        env_prefix = "PREFECT_LOGGING_"
        frozen = True

    console_level: str = "DEBUG"
    root_level: str = "WARNING"
    runner_level: str = "DEBUG"
    orion_level: str = "DEBUG"

    settings_path: Path = Path("~/.prefect/logging.yml").expanduser()
    log_directory: Path = Path("~/.prefect/logs").expanduser()


class Settings(BaseSettings):
    class Config:
        env_prefix = "PREFECT_"
        frozen = True

    # debug
    debug_mode: bool = False
    test_mode: bool = False

    # logging settings
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    # orion
    orion: OrionSettings = Field(default_factory=OrionSettings)


settings = Settings()
