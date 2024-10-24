import warnings
from typing import Optional
from urllib.parse import quote_plus

from pydantic import AliasChoices, AliasPath, Field, SecretStr, model_validator
from pydantic_settings import SettingsConfigDict
from typing_extensions import Literal, Self

from prefect.settings.base import PrefectBaseSettings


class ServerDatabaseSettings(PrefectBaseSettings):
    """
    Settings for controlling server database behavior
    """

    model_config = SettingsConfigDict(
        env_prefix="PREFECT_SERVER_DATABASE_",
        env_file=".env",
        extra="ignore",
    )

    connection_url: Optional[SecretStr] = Field(
        default=None,
        description="""
        A database connection URL in a SQLAlchemy-compatible
        format. Prefect currently supports SQLite and Postgres. Note that all
        Prefect database engines must use an async driver - for SQLite, use
        `sqlite+aiosqlite` and for Postgres use `postgresql+asyncpg`.

        SQLite in-memory databases can be used by providing the url
        `sqlite+aiosqlite:///file::memory:?cache=shared&uri=true&check_same_thread=false`,
        which will allow the database to be accessed by multiple threads. Note
        that in-memory databases can not be accessed from multiple processes and
        should only be used for simple tests.
        """,
        validation_alias=AliasChoices(
            AliasPath("connection_url"),
            "prefect_server_database_connection_url",
            "prefect_api_database_connection_url",
        ),
    )

    driver: Optional[Literal["postgresql+asyncpg", "sqlite+aiosqlite"]] = Field(
        default=None,
        description=(
            "The database driver to use when connecting to the database. "
            "If not set, the driver will be inferred from the connection URL."
        ),
        validation_alias=AliasChoices(
            AliasPath("driver"),
            "prefect_server_database_driver",
            "prefect_api_database_driver",
        ),
    )

    host: Optional[str] = Field(
        default=None,
        description="The database server host.",
        validation_alias=AliasChoices(
            AliasPath("host"),
            "prefect_server_database_host",
            "prefect_api_database_host",
        ),
    )

    port: Optional[int] = Field(
        default=None,
        description="The database server port.",
        validation_alias=AliasChoices(
            AliasPath("port"),
            "prefect_server_database_port",
            "prefect_api_database_port",
        ),
    )

    user: Optional[str] = Field(
        default=None,
        description="The user to use when connecting to the database.",
        validation_alias=AliasChoices(
            AliasPath("user"),
            "prefect_server_database_user",
            "prefect_api_database_user",
        ),
    )

    name: Optional[str] = Field(
        default=None,
        description="The name of the Prefect database on the remote server, or the path to the database file for SQLite.",
        validation_alias=AliasChoices(
            AliasPath("name"),
            "prefect_server_database_name",
            "prefect_api_database_name",
        ),
    )

    password: Optional[SecretStr] = Field(
        default=None,
        description="The password to use when connecting to the database. Should be kept secret.",
        validation_alias=AliasChoices(
            AliasPath("password"),
            "prefect_server_database_password",
            "prefect_api_database_password",
        ),
    )

    echo: bool = Field(
        default=False,
        description="If `True`, SQLAlchemy will log all SQL issued to the database. Defaults to `False`.",
        validation_alias=AliasChoices(
            AliasPath("echo"),
            "prefect_server_database_echo",
            "prefect_api_database_echo",
        ),
    )

    migrate_on_start: bool = Field(
        default=True,
        description="If `True`, the database will be migrated on application startup.",
        validation_alias=AliasChoices(
            AliasPath("migrate_on_start"),
            "prefect_server_database_migrate_on_start",
            "prefect_api_database_migrate_on_start",
        ),
    )

    timeout: Optional[float] = Field(
        default=10.0,
        description="A statement timeout, in seconds, applied to all database interactions made by the API. Defaults to 10 seconds.",
        validation_alias=AliasChoices(
            AliasPath("timeout"),
            "prefect_server_database_timeout",
            "prefect_api_database_timeout",
        ),
    )

    connection_timeout: Optional[float] = Field(
        default=5,
        description="A connection timeout, in seconds, applied to database connections. Defaults to `5`.",
        validation_alias=AliasChoices(
            AliasPath("connection_timeout"),
            "prefect_server_database_connection_timeout",
            "prefect_api_database_connection_timeout",
        ),
    )

    sqlalchemy_pool_size: Optional[int] = Field(
        default=None,
        description="Controls connection pool size when using a PostgreSQL database with the Prefect API. If not set, the default SQLAlchemy pool size will be used.",
        validation_alias=AliasChoices(
            AliasPath("sqlalchemy_pool_size"),
            "prefect_server_database_sqlalchemy_pool_size",
            "prefect_sqlalchemy_pool_size",
        ),
    )

    sqlalchemy_max_overflow: Optional[int] = Field(
        default=None,
        description="Controls maximum overflow of the connection pool when using a PostgreSQL database with the Prefect API. If not set, the default SQLAlchemy maximum overflow value will be used.",
        validation_alias=AliasChoices(
            AliasPath("sqlalchemy_max_overflow"),
            "prefect_server_database_sqlalchemy_max_overflow",
            "prefect_sqlalchemy_max_overflow",
        ),
    )

    @model_validator(mode="after")
    def emit_warnings(self) -> Self:  # noqa: F821
        """More post-hoc validation of settings, including warnings for misconfigurations."""
        warn_on_database_password_value_without_usage(self)
        return self


def warn_on_database_password_value_without_usage(settings: ServerDatabaseSettings):
    """
    Validator for settings warning if the database password is set but not used.
    """
    db_password = (
        settings.password.get_secret_value()
        if isinstance(settings.password, SecretStr)
        else None
    )
    api_db_connection_url = (
        settings.connection_url.get_secret_value()
        if isinstance(settings.connection_url, SecretStr)
        else settings.connection_url
    )

    if (
        db_password
        and api_db_connection_url is not None
        and "PREFECT_API_DATABASE_PASSWORD" not in api_db_connection_url
        and "PREFECT_SERVER_DATABASE_PASSWORD" not in api_db_connection_url
        and db_password not in api_db_connection_url
        and quote_plus(db_password) not in api_db_connection_url
    ):
        warnings.warn(
            "PREFECT_SERVER_DATABASE_PASSWORD is set but not included in the "
            "PREFECT_SERVER_DATABASE_CONNECTION_URL. "
            "The provided password will be ignored."
        )
    return settings
