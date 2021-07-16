from pydantic import BaseSettings, Field


class DatabaseSettings(BaseSettings):
    class Config:
        env_prefix = "ORION_DATABASE_"
        frozen = True

    connection_url: str = "sqlite+aiosqlite:///tmp/orion.db"
    echo: bool = True


class Settings(BaseSettings):
    class Config:
        env_prefix = "ORION_"
        frozen = True

    # debug
    test_mode = False

    # logging
    logging_level: str = "INFO"

    # database
    # using `default_factory` avoids instantiating the default value until the parent
    # settings class is instantiated
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
