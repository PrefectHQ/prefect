from pathlib import Path

from pydantic import BaseSettings, Field, validator


class LoggingSettings(BaseSettings):
    class Config:
        env_prefix = "PREFECT_LOGGING_"
        frozen = True

    console_level: str = "DEBUG"
    root_level: str = "WARNING"
    prefect_level: str = "DEBUG"

    settings_path: Path = Path("~/.prefect/logging.yml").expanduser()
    log_directory: Path = Path("~/.prefect/logs").expanduser()


class Settings(BaseSettings):
    class Config:
        env_prefix = "PREFECT_"
        frozen = True

    logging: LoggingSettings = Field(default_factory=LoggingSettings)
