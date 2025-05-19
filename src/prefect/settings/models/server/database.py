import warnings
from typing import Any, ClassVar, Optional
from urllib.parse import quote_plus

from pydantic import (
    AliasChoices,
    AliasPath,
    Field,
    SecretStr,
    model_validator,
)
from pydantic_settings import SettingsConfigDict
from typing_extensions import Literal, Self

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class SQLAlchemyTLSSettings(PrefectBaseSettings):
    """
    Settings for controlling SQLAlchemy mTLS context when
    using a PostgreSQL database.
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "database", "sqlalchemy", "connect_args", "tls")
    )

    enabled: bool = Field(
        default=False,
        description="Controls whether connected to mTLS enabled PostgreSQL when using a PostgreSQL database with the Prefect backend.",
    )

    ca_file: Optional[str] = Field(
        default=None,
        description="This configuration settings option specifies the path to PostgreSQL client certificate authority file.",
    )

    cert_file: Optional[str] = Field(
        default=None,
        description="This configuration settings option specifies the path to PostgreSQL client certificate file.",
    )

    key_file: Optional[str] = Field(
        default=None,
        description="This configuration settings option specifies the path to PostgreSQL client key file.",
    )

    check_hostname: bool = Field(
        default=True,
        description="This configuration settings option specifies whether to verify PostgreSQL server hostname.",
    )


class SQLAlchemyConnectArgsSettings(PrefectBaseSettings):
    """
    Settings for controlling SQLAlchemy connection behavior; note that these settings only take effect when
    using a PostgreSQL database.
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "database", "sqlalchemy", "connect_args")
    )

    application_name: Optional[str] = Field(
        default=None,
        description="Controls the application_name field for connections opened from the connection pool when using a PostgreSQL database with the Prefect backend.",
    )

    statement_cache_size: Optional[int] = Field(
        default=None,
        description="Controls statement cache size for PostgreSQL connections. Setting this to 0 is required when using PgBouncer in transaction mode. Defaults to None.",
    )

    prepared_statement_cache_size: Optional[int] = Field(
        default=None,
        description=(
            "Controls the size of the statement cache for PostgreSQL connections. "
            "When set to 0, statement caching is disabled. Defaults to None to use "
            "SQLAlchemy's default behavior."
        ),
    )

    tls: SQLAlchemyTLSSettings = Field(
        default_factory=SQLAlchemyTLSSettings,
        description="Settings for controlling SQLAlchemy mTLS behavior",
    )


class SQLAlchemySettings(PrefectBaseSettings):
    """
    Settings for controlling SQLAlchemy behavior; note that these settings only take effect when
    using a PostgreSQL database.
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "database", "sqlalchemy")
    )

    connect_args: SQLAlchemyConnectArgsSettings = Field(
        default_factory=SQLAlchemyConnectArgsSettings,
        description="Settings for controlling SQLAlchemy connection behavior",
    )

    pool_size: int = Field(
        default=5,
        description="Controls connection pool size of database connection pools from the Prefect backend.",
        validation_alias=AliasChoices(
            AliasPath("pool_size"),
            "prefect_server_database_sqlalchemy_pool_size",
            "prefect_sqlalchemy_pool_size",
        ),
    )

    pool_recycle: int = Field(
        default=3600,
        description="This setting causes the pool to recycle connections after the given number of seconds has passed; set it to -1 to avoid recycling entirely.",
    )

    pool_timeout: Optional[float] = Field(
        default=30.0,
        description="Number of seconds to wait before giving up on getting a connection from the pool. Defaults to 30 seconds.",
    )

    max_overflow: int = Field(
        default=10,
        description="Controls maximum overflow of the connection pool. To prevent overflow, set to -1.",
        validation_alias=AliasChoices(
            AliasPath("max_overflow"),
            "prefect_server_database_sqlalchemy_max_overflow",
            "prefect_sqlalchemy_max_overflow",
        ),
    )


class ServerDatabaseSettings(PrefectBaseSettings):
    """
    Settings for controlling server database behavior
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "database")
    )

    sqlalchemy: SQLAlchemySettings = Field(
        default_factory=SQLAlchemySettings,
        description="Settings for controlling SQLAlchemy behavior",
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
        description="A statement timeout, in seconds, applied to all database interactions made by the Prefect backend. Defaults to 10 seconds.",
        validation_alias=AliasChoices(
            AliasPath("timeout"),
            "prefect_server_database_timeout",
            "prefect_api_database_timeout",
        ),
    )

    connection_timeout: Optional[float] = Field(
        default=5.0,
        description="A connection timeout, in seconds, applied to database connections. Defaults to `5`.",
        validation_alias=AliasChoices(
            AliasPath("connection_timeout"),
            "prefect_server_database_connection_timeout",
            "prefect_api_database_connection_timeout",
        ),
    )

    # handle deprecated fields

    def __getattribute__(self, name: str) -> Any:
        if name in ["sqlalchemy_pool_size", "sqlalchemy_max_overflow"]:
            warnings.warn(
                f"Setting {name} has been moved to the `sqlalchemy` settings group.",
                DeprecationWarning,
            )
            field_name = name.replace("sqlalchemy_", "")
            return getattr(super().__getattribute__("sqlalchemy"), field_name)
        return super().__getattribute__(name)

    # validators

    @model_validator(mode="before")
    @classmethod
    def set_deprecated_sqlalchemy_settings_on_child_model_and_warn(
        cls, values: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Set deprecated settings on the child model.
        """
        # Initialize sqlalchemy settings if not present
        if "sqlalchemy" not in values:
            values["sqlalchemy"] = SQLAlchemySettings()

        if "sqlalchemy_pool_size" in values:
            warnings.warn(
                "`sqlalchemy_pool_size` has been moved to the `sqlalchemy` settings group as `pool_size`.",
                DeprecationWarning,
            )
            if "pool_size" not in values["sqlalchemy"].model_fields_set:
                values["sqlalchemy"].pool_size = values["sqlalchemy_pool_size"]

        if "sqlalchemy_max_overflow" in values:
            warnings.warn(
                "`sqlalchemy_max_overflow` has been moved to the `sqlalchemy` settings group as `max_overflow`.",
                DeprecationWarning,
            )
            if "max_overflow" not in values["sqlalchemy"].model_fields_set:
                values["sqlalchemy"].max_overflow = values["sqlalchemy_max_overflow"]

        return values

    @model_validator(mode="after")
    def emit_warnings(self) -> Self:  # noqa: F821
        """More post-hoc validation of settings, including warnings for misconfigurations."""
        warn_on_database_password_value_without_usage(self)
        return self


def warn_on_database_password_value_without_usage(
    settings: ServerDatabaseSettings,
) -> None:
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
    return None
