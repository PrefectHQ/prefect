"""
Prefect settings are defined using `BaseSettings` from `pydantic_settings`. `BaseSettings` can load setting values
from system environment variables and each additionally specified `env_file`.

The recommended user-facing way to access Prefect settings at this time is to import specific setting objects directly,
like `from prefect.settings import PREFECT_API_URL; print(PREFECT_API_URL.value())`.

Importantly, we replace the `callback` mechanism for updating settings with an "after" model_validator that updates dependent settings.
After https://github.com/pydantic/pydantic/issues/9789 is resolved, we will be able to define context-aware defaults
for settings, at which point we will not need to use the "after" model_validator.
"""

import os
import re
import sys
import warnings
from contextlib import contextmanager
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Dict,
    Generator,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_args,
)
from urllib.parse import quote_plus, urlparse

import toml
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    Secret,
    SecretStr,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    TypeAdapter,
    ValidationError,
    model_serializer,
    model_validator,
)
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from typing_extensions import Literal, Self

from prefect.exceptions import ProfileSettingsValidationError
from prefect.types import ClientRetryExtraCodes, LogLevel
from prefect.utilities.collections import visit_collection
from prefect.utilities.pydantic import handle_secret_render

T = TypeVar("T")

DEFAULT_PREFECT_HOME = Path.home() / ".prefect"
DEFAULT_PROFILES_PATH = Path(__file__).parent.joinpath("profiles.toml")
_SECRET_TYPES: Tuple[Type, ...] = (Secret, SecretStr)


def env_var_to_attr_name(env_var: str) -> str:
    """
    Convert an environment variable name to an attribute name.
    """
    return env_var.replace("PREFECT_", "").lower()


def is_test_mode() -> bool:
    """Check if the current process is in test mode."""
    return bool(os.getenv("PREFECT_TEST_MODE") or os.getenv("PREFECT_UNIT_TEST_MODE"))


class Setting:
    """Mimics the old Setting object for compatibility with existing code."""

    def __init__(self, name: str, default: Any, type_: Any):
        self._name = name
        self._default = default
        self._type = type_

    @property
    def name(self):
        return self._name

    @property
    def field_name(self):
        return env_var_to_attr_name(self.name)

    @property
    def is_secret(self):
        if self._type in _SECRET_TYPES:
            return True
        for secret_type in _SECRET_TYPES:
            if secret_type in get_args(self._type):
                return True
        return False

    def default(self):
        return self._default

    def value(self: Self) -> Any:
        if self.name == "PREFECT_TEST_SETTING":
            if "PREFECT_TEST_MODE" in os.environ:
                return get_current_settings().test_setting
            else:
                return None

        current_value = getattr(get_current_settings(), self.field_name)
        if isinstance(current_value, _SECRET_TYPES):
            return current_value.get_secret_value()
        return current_value

    def value_from(self: Self, settings: "Settings") -> Any:
        current_value = getattr(settings, self.field_name)
        if isinstance(current_value, _SECRET_TYPES):
            return current_value.get_secret_value()
        return current_value

    def __bool__(self) -> bool:
        return bool(self.value())

    def __str__(self) -> str:
        return str(self.value())

    def __repr__(self) -> str:
        return f"<{self.name}: {self._type!r}>"

    def __eq__(self, __o: object) -> bool:
        return __o.__eq__(self.value())

    def __hash__(self) -> int:
        return hash((type(self), self.name))


########################################################################
# Define post init validators for use in an "after" model_validator,
# core logic will remain similar after context-aware defaults are supported


def default_ui_url(settings: "Settings") -> Optional[str]:
    value = settings.ui_url
    if value is not None:
        return value

    # Otherwise, infer a value from the API URL
    ui_url = api_url = settings.api_url

    if not api_url:
        return None

    cloud_url = settings.cloud_api_url
    cloud_ui_url = settings.cloud_ui_url
    if api_url.startswith(cloud_url):
        ui_url = ui_url.replace(cloud_url, cloud_ui_url)

    if ui_url.endswith("/api"):
        # Handles open-source APIs
        ui_url = ui_url[:-4]

    # Handles Cloud APIs with content after `/api`
    ui_url = ui_url.replace("/api/", "/")

    # Update routing
    ui_url = ui_url.replace("/accounts/", "/account/")
    ui_url = ui_url.replace("/workspaces/", "/workspace/")

    return ui_url


def default_cloud_ui_url(settings) -> Optional[str]:
    value = settings.cloud_ui_url
    if value is not None:
        return value

    # Otherwise, infer a value from the API URL
    ui_url = api_url = settings.cloud_api_url

    if re.match(r"^https://api[\.\w]*.prefect.[^\.]+/", api_url):
        ui_url = ui_url.replace("https://api", "https://app", 1)

    if ui_url.endswith("/api"):
        ui_url = ui_url[:-4]

    return ui_url


def max_log_size_smaller_than_batch_size(values):
    """
    Validator for settings asserting the batch size and match log size are compatible
    """
    if values["logging_to_api_batch_size"] < values["logging_to_api_max_log_size"]:
        raise ValueError(
            "`PREFECT_LOGGING_TO_API_MAX_LOG_SIZE` cannot be larger than"
            " `PREFECT_LOGGING_TO_API_BATCH_SIZE`"
        )
    return values


def warn_on_database_password_value_without_usage(values):
    """
    Validator for settings warning if the database password is set but not used.
    """
    db_password = (
        v.get_secret_value()
        if (v := values["api_database_password"]) and hasattr(v, "get_secret_value")
        else None
    )
    api_db_connection_url = (
        values["api_database_connection_url"].get_secret_value()
        if hasattr(values["api_database_connection_url"], "get_secret_value")
        else values["api_database_connection_url"]
    )
    if (
        db_password
        and api_db_connection_url is not None
        and ("PREFECT_API_DATABASE_PASSWORD" not in api_db_connection_url)
        and db_password not in api_db_connection_url
        and quote_plus(db_password) not in api_db_connection_url
    ):
        warnings.warn(
            "PREFECT_API_DATABASE_PASSWORD is set but not included in the "
            "PREFECT_API_DATABASE_CONNECTION_URL. "
            "The provided password will be ignored."
        )
    return values


def warn_on_misconfigured_api_url(values):
    """
    Validator for settings warning if the API URL is misconfigured.
    """
    api_url = values["api_url"]
    if api_url is not None:
        misconfigured_mappings = {
            "app.prefect.cloud": (
                "`PREFECT_API_URL` points to `app.prefect.cloud`. Did you"
                " mean `api.prefect.cloud`?"
            ),
            "account/": (
                "`PREFECT_API_URL` uses `/account/` but should use `/accounts/`."
            ),
            "workspace/": (
                "`PREFECT_API_URL` uses `/workspace/` but should use `/workspaces/`."
            ),
        }
        warnings_list = []

        for misconfig, warning in misconfigured_mappings.items():
            if misconfig in api_url:
                warnings_list.append(warning)

        parsed_url = urlparse(api_url)
        if parsed_url.path and not parsed_url.path.startswith("/api"):
            warnings_list.append(
                "`PREFECT_API_URL` should have `/api` after the base URL."
            )

        if warnings_list:
            example = 'e.g. PREFECT_API_URL="https://api.prefect.cloud/api/accounts/[ACCOUNT-ID]/workspaces/[WORKSPACE-ID]"'
            warnings_list.append(example)

            warnings.warn("\n".join(warnings_list), stacklevel=2)

    return values


def default_database_connection_url(settings: "Settings") -> SecretStr:
    value = None
    if settings.api_database_driver == "postgresql+asyncpg":
        required = [
            "api_database_host",
            "api_database_user",
            "api_database_name",
            "api_database_password",
        ]
        missing = [attr for attr in required if getattr(settings, attr) is None]
        if missing:
            raise ValueError(
                f"Missing required database connection settings: {', '.join(missing)}"
            )

        from sqlalchemy import URL

        return URL(
            drivername=settings.api_database_driver,
            host=settings.api_database_host,
            port=settings.api_database_port or 5432,
            username=settings.api_database_user,
            password=(
                settings.api_database_password.get_secret_value()
                if settings.api_database_password
                else None
            ),
            database=settings.api_database_name,
            query=[],  # type: ignore
        ).render_as_string(hide_password=False)

    elif settings.api_database_driver == "sqlite+aiosqlite":
        if settings.api_database_name:
            value = f"{settings.api_database_driver}:///{settings.api_database_name}"
        else:
            value = f"sqlite+aiosqlite:///{settings.home}/prefect.db"

    elif settings.api_database_driver:
        raise ValueError(f"Unsupported database driver: {settings.api_database_driver}")

    value = value if value else f"sqlite+aiosqlite:///{settings.home}/prefect.db"
    return SecretStr(value)


###########################################################################
# Settings Loader


def _get_profiles_path() -> Path:
    """Helper to get the profiles path"""

    if is_test_mode():
        return DEFAULT_PROFILES_PATH
    if env_path := os.getenv("PREFECT_PROFILES_PATH"):
        return Path(env_path)
    if not (DEFAULT_PREFECT_HOME / "profiles.toml").exists():
        return DEFAULT_PROFILES_PATH
    return DEFAULT_PREFECT_HOME / "profiles.toml"


class ProfileSettingsTomlLoader(PydanticBaseSettingsSource):
    """
    Custom pydantic settings source to load profile settings from a toml file.

    See https://docs.pydantic.dev/latest/concepts/pydantic_settings/#customise-settings-sources
    """

    def __init__(self, settings_cls: Type[BaseSettings]):
        super().__init__(settings_cls)
        self.settings_cls = settings_cls
        self.profiles_path = _get_profiles_path()
        self.profile_settings = self._load_profile_settings()

    def _load_profile_settings(self) -> Dict[str, Any]:
        """Helper method to load the profile settings from the profiles.toml file"""

        if not self.profiles_path.exists():
            return {}

        try:
            all_profile_data = toml.load(self.profiles_path)
        except toml.TomlDecodeError:
            warnings.warn(
                f"Failed to load profiles from {self.profiles_path}. Please ensure the file is valid TOML."
            )
            return {}

        if (
            sys.argv[0].endswith("/prefect")
            and len(sys.argv) >= 3
            and sys.argv[1] == "--profile"
        ):
            active_profile = sys.argv[2]

        else:
            active_profile = os.environ.get("PREFECT_PROFILE") or all_profile_data.get(
                "active"
            )

        profiles_data = all_profile_data.get("profiles", {})

        if not active_profile or active_profile not in profiles_data:
            return {}

        return profiles_data[active_profile]

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> Tuple[Any, str, bool]:
        """Concrete implementation to get the field value from the profile settings"""
        value = self.profile_settings.get(f"PREFECT_{field_name.upper()}")
        return value, field_name, self.field_is_complex(field)

    def __call__(self) -> Dict[str, Any]:
        """Called by pydantic to get the settings from our custom source"""
        if is_test_mode():
            return {}
        profile_settings: Dict[str, Any] = {}
        for field_name, field in self.settings_cls.model_fields.items():
            value, key, is_complex = self.get_field_value(field, field_name)
            if value is not None:
                prepared_value = self.prepare_field_value(
                    field_name, field, value, is_complex
                )
                profile_settings[key] = prepared_value
        return profile_settings


###########################################################################
# Settings


class Settings(BaseSettings):
    """
    Settings for Prefect using Pydantic settings.

    See https://docs.pydantic.dev/latest/concepts/pydantic_settings
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PREFECT_",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """
        Define an order for Prefect settings sources.

        The order of the returned callables decides the priority of inputs; first item is the highest priority.

        See https://docs.pydantic.dev/latest/concepts/pydantic_settings/#customise-settings-sources
        """
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            ProfileSettingsTomlLoader(settings_cls),
        )

    ###########################################################################
    # CLI

    cli_colors: bool = Field(
        default=True,
        description="If True, use colors in CLI output. If `False`, output will not include colors codes.",
    )

    cli_prompt: Optional[bool] = Field(
        default=None,
        description="If `True`, use interactive prompts in CLI commands. If `False`, no interactive prompts will be used. If `None`, the value will be dynamically determined based on the presence of an interactive-enabled terminal.",
    )

    cli_wrap_lines: bool = Field(
        default=True,
        description="If `True`, wrap text by inserting new lines in long lines in CLI output. If `False`, output will not be wrapped.",
    )

    ###########################################################################
    # Testing

    test_mode: bool = Field(
        default=False,
        description="If `True`, places the API in test mode. This may modify behavior to facilitate testing.",
    )

    unit_test_mode: bool = Field(
        default=False,
        description="This setting only exists to facilitate unit testing. If `True`, code is executing in a unit test context. Defaults to `False`.",
    )

    unit_test_loop_debug: bool = Field(
        default=True,
        description="If `True` turns on debug mode for the unit testing event loop.",
    )

    test_setting: Optional[Any] = Field(
        default="FOO",
        description="This setting only exists to facilitate unit testing. If in test mode, this setting will return its value. Otherwise, it returns `None`.",
    )

    ###########################################################################
    # Results settings

    results_default_serializer: str = Field(
        default="pickle",
        description="The default serializer to use when not otherwise specified.",
    )

    results_persist_by_default: bool = Field(
        default=False,
        description="The default setting for persisting results when not otherwise specified.",
    )

    ###########################################################################
    # API settings

    api_url: Optional[str] = Field(
        default=None,
        description="The URL of the Prefect API. If not set, the client will attempt to infer it.",
    )
    api_key: Optional[SecretStr] = Field(
        default=None,
        description="The API key used for authentication with the Prefect API. Should be kept secret.",
    )

    api_tls_insecure_skip_verify: bool = Field(
        default=False,
        description="If `True`, disables SSL checking to allow insecure requests. This is recommended only during development, e.g. when using self-signed certificates.",
    )

    api_ssl_cert_file: Optional[str] = Field(
        default=os.environ.get("SSL_CERT_FILE"),
        description="This configuration settings option specifies the path to an SSL certificate file.",
    )

    api_enable_http2: bool = Field(
        default=False,
        description="If true, enable support for HTTP/2 for communicating with an API. If the API does not support HTTP/2, this will have no effect and connections will be made via HTTP/1.1.",
    )

    api_request_timeout: float = Field(
        default=60.0,
        description="The default timeout for requests to the API",
    )

    api_blocks_register_on_start: bool = Field(
        default=True,
        description="If set, any block types that have been imported will be registered with the backend on application startup. If not set, block types must be manually registered.",
    )

    api_log_retryable_errors: bool = Field(
        default=False,
        description="If `True`, log retryable errors in the API and it's services.",
    )

    api_default_limit: int = Field(
        default=200,
        description="The default limit applied to queries that can return multiple objects, such as `POST /flow_runs/filter`.",
    )

    api_task_cache_key_max_length: int = Field(
        default=2000,
        description="The maximum number of characters allowed for a task run cache key.",
    )

    api_max_flow_run_graph_nodes: int = Field(
        default=10000,
        description="The maximum size of a flow run graph on the v2 API",
    )

    api_max_flow_run_graph_artifacts: int = Field(
        default=10000,
        description="The maximum number of artifacts to show on a flow run graph on the v2 API",
    )

    ###########################################################################
    # API Database settings

    api_database_connection_url: Optional[SecretStr] = Field(
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
    )

    api_database_driver: Optional[
        Literal["postgresql+asyncpg", "sqlite+aiosqlite"]
    ] = Field(
        default=None,
        description=(
            "The database driver to use when connecting to the database. "
            "If not set, the driver will be inferred from the connection URL."
        ),
    )

    api_database_host: Optional[str] = Field(
        default=None,
        description="The database server host.",
    )

    api_database_port: Optional[int] = Field(
        default=None,
        description="The database server port.",
    )

    api_database_user: Optional[str] = Field(
        default=None,
        description="The user to use when connecting to the database.",
    )

    api_database_name: Optional[str] = Field(
        default=None,
        description="The name of the Prefect database on the remote server, or the path to the database file for SQLite.",
    )

    api_database_password: Optional[SecretStr] = Field(
        default=None,
        description="The password to use when connecting to the database. Should be kept secret.",
    )

    api_database_echo: bool = Field(
        default=False,
        description="If `True`, SQLAlchemy will log all SQL issued to the database. Defaults to `False`.",
    )

    api_database_migrate_on_start: bool = Field(
        default=True,
        description="If `True`, the database will be migrated on application startup.",
    )

    api_database_timeout: Optional[float] = Field(
        default=10.0,
        description="A statement timeout, in seconds, applied to all database interactions made by the API. Defaults to 10 seconds.",
    )

    api_database_connection_timeout: Optional[float] = Field(
        default=5,
        description="A connection timeout, in seconds, applied to database connections. Defaults to `5`.",
    )

    ###########################################################################
    # API Services settings

    api_services_scheduler_enabled: bool = Field(
        default=True,
        description="Whether or not to start the scheduler service in the server application.",
    )

    api_services_scheduler_loop_seconds: float = Field(
        default=60,
        description="""
        The scheduler loop interval, in seconds. This determines
        how often the scheduler will attempt to schedule new flow runs, but has no
        impact on how quickly either flow runs or task runs are actually executed.
        Defaults to `60`.
        """,
    )

    api_services_scheduler_deployment_batch_size: int = Field(
        default=100,
        description="""
        The number of deployments the scheduler will attempt to
        schedule in a single batch. If there are more deployments than the batch
        size, the scheduler immediately attempts to schedule the next batch; it
        does not sleep for `scheduler_loop_seconds` until it has visited every
        deployment once. Defaults to `100`.
        """,
    )

    api_services_scheduler_max_runs: int = Field(
        default=100,
        description="""
        The scheduler will attempt to schedule up to this many
        auto-scheduled runs in the future. Note that runs may have fewer than
        this many scheduled runs, depending on the value of
        `scheduler_max_scheduled_time`.  Defaults to `100`.
        """,
    )

    api_services_scheduler_min_runs: int = Field(
        default=3,
        description="""
        The scheduler will attempt to schedule at least this many
        auto-scheduled runs in the future. Note that runs may have more than
        this many scheduled runs, depending on the value of
        `scheduler_min_scheduled_time`.  Defaults to `3`.
        """,
    )

    api_services_scheduler_max_scheduled_time: timedelta = Field(
        default=timedelta(days=100),
        description="""
        The scheduler will create new runs up to this far in the
        future. Note that this setting will take precedence over
        `scheduler_max_runs`: if a flow runs once a month and
        `scheduler_max_scheduled_time` is three months, then only three runs will be
        scheduled. Defaults to 100 days (`8640000` seconds).
        """,
    )

    api_services_scheduler_min_scheduled_time: timedelta = Field(
        default=timedelta(hours=1),
        description="""
        The scheduler will create new runs at least this far in the
        future. Note that this setting will take precedence over `scheduler_min_runs`:
        if a flow runs every hour and `scheduler_min_scheduled_time` is three hours,
        then three runs will be scheduled even if `scheduler_min_runs` is 1. Defaults to
        """,
    )

    api_services_scheduler_insert_batch_size: int = Field(
        default=500,
        description="""
        The number of runs the scheduler will attempt to insert in a single batch.
        Defaults to `500`.
        """,
    )

    api_services_late_runs_enabled: bool = Field(
        default=True,
        description="Whether or not to start the late runs service in the server application.",
    )

    api_services_late_runs_loop_seconds: float = Field(
        default=5,
        description="""
        The late runs service will look for runs to mark as late this often. Defaults to `5`.
        """,
    )

    api_services_late_runs_after_seconds: timedelta = Field(
        default=timedelta(seconds=15),
        description="""
        The late runs service will mark runs as late after they have exceeded their scheduled start time by this many seconds. Defaults to `5` seconds.
        """,
    )

    api_services_pause_expirations_loop_seconds: float = Field(
        default=5,
        description="""
        The pause expiration service will look for runs to mark as failed this often. Defaults to `5`.
        """,
    )

    api_services_cancellation_cleanup_enabled: bool = Field(
        default=True,
        description="Whether or not to start the cancellation cleanup service in the server application.",
    )

    api_services_cancellation_cleanup_loop_seconds: float = Field(
        default=20,
        description="""
        The cancellation cleanup service will look non-terminal tasks and subflows this often. Defaults to `20`.
        """,
    )

    api_services_foreman_enabled: bool = Field(
        default=True,
        description="Whether or not to start the Foreman service in the server application.",
    )

    api_services_foreman_loop_seconds: float = Field(
        default=15,
        description="""
        The number of seconds to wait between each iteration of the Foreman loop which checks
        for offline workers and updates work pool status. Defaults to `15`.
        """,
    )

    api_services_foreman_inactivity_heartbeat_multiple: int = Field(
        default=3,
        description="""
        The number of heartbeats that must be missed before a worker is marked as offline. Defaults to `3`.
        """,
    )

    api_services_foreman_fallback_heartbeat_interval_seconds: int = Field(
        default=30,
        description="""
        The number of seconds to use for online/offline evaluation if a worker's heartbeat
        interval is not set. Defaults to `30`.
        """,
    )

    api_services_foreman_deployment_last_polled_timeout_seconds: int = Field(
        default=60,
        description="""
        The number of seconds before a deployment is marked as not ready if it has not been
        polled. Defaults to `60`.
        """,
    )

    api_services_foreman_work_queue_last_polled_timeout_seconds: int = Field(
        default=60,
        description="""
        The number of seconds before a work queue is marked as not ready if it has not been
        polled. Defaults to `60`.
        """,
    )

    api_services_task_run_recorder_enabled: bool = Field(
        default=True,
        description="Whether or not to start the task run recorder service in the server application.",
    )

    api_services_flow_run_notifications_enabled: bool = Field(
        default=True,
        description="""
        Whether or not to start the flow run notifications service in the server application.
        If disabled, you will need to run this service separately to send flow run notifications.
        """,
    )

    api_services_pause_expirations_enabled: bool = Field(
        default=True,
        description="""
        Whether or not to start the paused flow run expiration service in the server
        application. If disabled, paused flows that have timed out will remain in a Paused state
        until a resume attempt.
        """,
    )

    ###########################################################################
    # Cloud settings

    cloud_api_url: str = Field(
        default="https://api.prefect.cloud/api",
        description="API URL for Prefect Cloud. Used for authentication.",
    )

    cloud_ui_url: Optional[str] = Field(
        default=None,
        description="The URL of the Prefect Cloud UI. If not set, the client will attempt to infer it.",
    )

    ###########################################################################
    # Logging settings

    logging_level: LogLevel = Field(
        default="INFO",
        description="The default logging level for Prefect loggers.",
    )

    logging_internal_level: LogLevel = Field(
        default="ERROR",
        description="The default logging level for Prefect's internal machinery loggers.",
    )

    logging_server_level: LogLevel = Field(
        default="WARNING",
        description="The default logging level for the Prefect API server.",
    )

    logging_settings_path: Optional[Path] = Field(
        default=None,
        description="The path to a custom YAML logging configuration file.",
    )

    logging_extra_loggers: Annotated[
        Union[str, list[str], None],
        AfterValidator(lambda v: [n.strip() for n in v.split(",")] if v else []),
    ] = Field(
        default=None,
        description="Additional loggers to attach to Prefect logging at runtime.",
    )

    logging_log_prints: bool = Field(
        default=False,
        description="If `True`, `print` statements in flows and tasks will be redirected to the Prefect logger for the given run.",
    )

    logging_to_api_enabled: bool = Field(
        default=True,
        description="If `True`, logs will be sent to the API.",
    )

    logging_to_api_batch_interval: float = Field(
        default=2.0,
        description="The number of seconds between batched writes of logs to the API.",
    )

    logging_to_api_batch_size: int = Field(
        default=4_000_000,
        description="The number of logs to batch before sending to the API.",
    )

    logging_to_api_max_log_size: int = Field(
        default=1_000_000,
        description="The maximum size in bytes for a single log.",
    )

    logging_to_api_when_missing_flow: Literal["warn", "error", "ignore"] = Field(
        default="warn",
        description="""
        Controls the behavior when loggers attempt to send logs to the API handler from outside of a flow.
        
        All logs sent to the API must be associated with a flow run. The API log handler can
        only be used outside of a flow by manually providing a flow run identifier. Logs
        that are not associated with a flow run will not be sent to the API. This setting can
        be used to determine if a warning or error is displayed when the identifier is missing.

        The following options are available:

        - "warn": Log a warning message.
        - "error": Raise an error.
        - "ignore": Do not log a warning message or raise an error.
        """,
    )

    logging_colors: bool = Field(
        default=True,
        description="If `True`, use colors in CLI output. If `False`, output will not include colors codes.",
    )

    logging_markup: bool = Field(
        default=False,
        description="""
        Whether to interpret strings wrapped in square brackets as a style.
        This allows styles to be conveniently added to log messages, e.g.
        `[red]This is a red message.[/red]`. However, the downside is, if enabled,
        strings that contain square brackets may be inaccurately interpreted and
        lead to incomplete output, e.g.
        `[red]This is a red message.[/red]` may be interpreted as
        `[red]This is a red message.[/red]`.
        """,
    )

    ###########################################################################
    # Server settings

    server_api_host: str = Field(
        default="127.0.0.1",
        description="The API's host address (defaults to `127.0.0.1`).",
    )

    server_api_port: int = Field(
        default=4200,
        description="The API's port address (defaults to `4200`).",
    )

    server_api_keepalive_timeout: int = Field(
        default=5,
        description="""
        The API's keep alive timeout (defaults to `5`).
        Refer to https://www.uvicorn.org/settings/#timeouts for details.

        When the API is hosted behind a load balancer, you may want to set this to a value
        greater than the load balancer's idle timeout.

        Note this setting only applies when calling `prefect server start`; if hosting the
        API with another tool you will need to configure this there instead.
        """,
    )

    server_csrf_protection_enabled: bool = Field(
        default=False,
        description="""
        Controls the activation of CSRF protection for the Prefect server API.

        When enabled (`True`), the server enforces CSRF validation checks on incoming
        state-changing requests (POST, PUT, PATCH, DELETE), requiring a valid CSRF
        token to be included in the request headers or body. This adds a layer of
        security by preventing unauthorized or malicious sites from making requests on
        behalf of authenticated users.

        It is recommended to enable this setting in production environments where the
        API is exposed to web clients to safeguard against CSRF attacks.

        Note: Enabling this setting requires corresponding support in the client for
        CSRF token management. See PREFECT_CLIENT_CSRF_SUPPORT_ENABLED for more.
        """,
    )

    server_csrf_token_expiration: timedelta = Field(
        default=timedelta(hours=1),
        description="""
        Specifies the duration for which a CSRF token remains valid after being issued
        by the server.

        The default expiration time is set to 1 hour, which offers a reasonable
        compromise. Adjust this setting based on your specific security requirements
        and usage patterns.
        """,
    )

    server_cors_allowed_origins: str = Field(
        default="*",
        description="""
        A comma-separated list of origins that are authorized to make cross-origin requests to the API.

        By default, this is set to `*`, which allows requests from all origins.
        """,
    )

    server_cors_allowed_methods: str = Field(
        default="*",
        description="""
        A comma-separated list of methods that are authorized to make cross-origin requests to the API.

        By default, this is set to `*`, which allows requests from all methods.
        """,
    )

    server_cors_allowed_headers: str = Field(
        default="*",
        description="""
        A comma-separated list of headers that are authorized to make cross-origin requests to the API.

        By default, this is set to `*`, which allows requests from all headers.
        """,
    )

    server_allow_ephemeral_mode: bool = Field(
        default=False,
        description="""
        Controls whether or not a subprocess server can be started when no API URL is provided.
        """,
    )

    server_ephemeral_startup_timeout_seconds: int = Field(
        default=10,
        description="""
        The number of seconds to wait for the server to start when ephemeral mode is enabled.
        Defaults to `10`.
        """,
    )

    server_analytics_enabled: bool = Field(
        default=True,
        description="""
        When enabled, Prefect sends anonymous data (e.g. count of flow runs, package version)
        on server startup to help us improve our product.
        """,
    )

    ###########################################################################
    # UI settings

    ui_enabled: bool = Field(
        default=True,
        description="Whether or not to serve the Prefect UI.",
    )

    ui_url: Optional[str] = Field(
        default=None,
        description="The URL of the Prefect UI. If not set, the client will attempt to infer it.",
    )

    ui_api_url: Optional[str] = Field(
        default=None,
        description="The connection url for communication from the UI to the API. Defaults to `PREFECT_API_URL` if set. Otherwise, the default URL is generated from `PREFECT_SERVER_API_HOST` and `PREFECT_SERVER_API_PORT`.",
    )

    ui_serve_base: str = Field(
        default="/",
        description="The base URL path to serve the Prefect UI from.",
    )

    ui_static_directory: Optional[str] = Field(
        default=None,
        description="The directory to serve static files from. This should be used when running into permissions issues when attempting to serve the UI from the default directory (for example when running in a Docker container).",
    )

    ###########################################################################
    # Events settings

    api_services_triggers_enabled: bool = Field(
        default=True,
        description="Whether or not to start the triggers service in the server application.",
    )

    api_services_event_persister_enabled: bool = Field(
        default=True,
        description="Whether or not to start the event persister service in the server application.",
    )

    api_services_event_persister_batch_size: int = Field(
        default=20,
        gt=0,
        description="The number of events the event persister will attempt to insert in one batch.",
    )

    api_services_event_persister_flush_interval: float = Field(
        default=5,
        gt=0.0,
        description="The maximum number of seconds between flushes of the event persister.",
    )

    api_events_stream_out_enabled: bool = Field(
        default=True,
        description="Whether or not to stream events out to the API via websockets.",
    )

    api_enable_metrics: bool = Field(
        default=False,
        description="Whether or not to enable Prometheus metrics in the API.",
    )

    api_events_related_resource_cache_ttl: timedelta = Field(
        default=timedelta(minutes=5),
        description="The number of seconds to cache related resources for in the API.",
    )

    client_enable_metrics: bool = Field(
        default=False,
        description="Whether or not to enable Prometheus metrics in the client.",
    )

    client_metrics_port: int = Field(
        default=4201, description="The port to expose the client Prometheus metrics on."
    )

    events_maximum_labels_per_resource: int = Field(
        default=500,
        description="The maximum number of labels a resource may have.",
    )

    events_maximum_related_resources: int = Field(
        default=500,
        description="The maximum number of related resources an Event may have.",
    )

    events_maximum_size_bytes: int = Field(
        default=1_500_000,
        description="The maximum size of an Event when serialized to JSON",
    )

    events_expired_bucket_buffer: timedelta = Field(
        default=timedelta(seconds=60),
        description="The amount of time to retain expired automation buckets",
    )

    events_proactive_granularity: timedelta = Field(
        default=timedelta(seconds=5),
        description="How frequently proactive automations are evaluated",
    )

    events_retention_period: timedelta = Field(
        default=timedelta(days=7),
        description="The amount of time to retain events in the database.",
    )

    events_maximum_websocket_backfill: timedelta = Field(
        default=timedelta(minutes=15),
        description="The maximum range to look back for backfilling events for a websocket subscriber.",
    )

    events_websocket_backfill_page_size: int = Field(
        default=250,
        gt=0,
        description="The page size for the queries to backfill events for websocket subscribers.",
    )

    ###########################################################################
    # uncategorized

    home: Annotated[Path, BeforeValidator(lambda x: Path(x).expanduser())] = Field(
        default=Path("~") / ".prefect",
        description="The path to the Prefect home directory. Defaults to ~/.prefect",
    )
    debug_mode: bool = Field(
        default=False,
        description="If True, enables debug mode which may provide additional logging and debugging features.",
    )

    silence_api_url_misconfiguration: bool = Field(
        default=False,
        description="""
        If `True`, disable the warning when a user accidentally misconfigure its `PREFECT_API_URL`
        Sometimes when a user manually set `PREFECT_API_URL` to a custom url,reverse-proxy for example,
        we would like to silence this warning so we will set it to `FALSE`.
        """,
    )

    client_max_retries: int = Field(
        default=5,
        ge=0,
        description="""
        The maximum number of retries to perform on failed HTTP requests.
        Defaults to 5. Set to 0 to disable retries.
        See `PREFECT_CLIENT_RETRY_EXTRA_CODES` for details on which HTTP status codes are
        retried.
        """,
    )

    client_retry_jitter_factor: float = Field(
        default=0.2,
        ge=0.0,
        description="""
        A value greater than or equal to zero to control the amount of jitter added to retried
        client requests. Higher values introduce larger amounts of jitter.
        Set to 0 to disable jitter. See `clamped_poisson_interval` for details on the how jitter
        can affect retry lengths.
        """,
    )

    client_retry_extra_codes: ClientRetryExtraCodes = Field(
        default_factory=set,
        description="""
        A list of extra HTTP status codes to retry on. Defaults to an empty list.
        429, 502 and 503 are always retried. Please note that not all routes are idempotent and retrying
        may result in unexpected behavior.
        """,
        examples=["404,429,503", "429", {404, 429, 503}],
    )

    client_csrf_support_enabled: bool = Field(
        default=True,
        description="""
        Determines if CSRF token handling is active in the Prefect client for API
        requests.

        When enabled (`True`), the client automatically manages CSRF tokens by
        retrieving, storing, and including them in applicable state-changing requests
        """,
    )

    experimental_warn: bool = Field(
        default=True,
        description="If `True`, warn on usage of experimental features.",
    )

    profiles_path: Optional[Path] = Field(
        default=None,
        description="The path to a profiles configuration file.",
    )

    tasks_refresh_cache: bool = Field(
        default=False,
        description="If `True`, enables a refresh of cached results: re-executing the task will refresh the cached results.",
    )

    task_default_retries: int = Field(
        default=0,
        ge=0,
        description="This value sets the default number of retries for all tasks.",
    )

    task_default_retry_delay_seconds: Union[int, float, list[float]] = Field(
        default=0,
        description="This value sets the default retry delay seconds for all tasks.",
    )

    task_run_tag_concurrency_slot_wait_seconds: int = Field(
        default=30,
        ge=0,
        description="The number of seconds to wait before retrying when a task run cannot secure a concurrency slot from the server.",
    )

    flow_default_retries: int = Field(
        default=0,
        ge=0,
        description="This value sets the default number of retries for all flows.",
    )

    flow_default_retry_delay_seconds: Union[int, float] = Field(
        default=0,
        description="This value sets the retry delay seconds for all flows.",
    )

    local_storage_path: Optional[Path] = Field(
        default=None,
        description="The path to a block storage directory to store things in.",
    )

    memo_store_path: Optional[Path] = Field(
        default=None,
        description="The path to the memo store file.",
    )

    memoize_block_auto_registration: bool = Field(
        default=True,
        description="Controls whether or not block auto-registration on start",
    )

    sqlalchemy_pool_size: Optional[int] = Field(
        default=None,
        description="Controls connection pool size when using a PostgreSQL database with the Prefect API. If not set, the default SQLAlchemy pool size will be used.",
    )

    sqlalchemy_max_overflow: Optional[int] = Field(
        default=None,
        description="Controls maximum overflow of the connection pool when using a PostgreSQL database with the Prefect API. If not set, the default SQLAlchemy maximum overflow value will be used.",
    )

    async_fetch_state_result: bool = Field(
        default=False,
        description="""
        Determines whether `State.result()` fetches results automatically or not.
        In Prefect 2.6.0, the `State.result()` method was updated to be async
        to facilitate automatic retrieval of results from storage which means when
        writing async code you must `await` the call. For backwards compatibility,
        the result is not retrieved by default for async users. You may opt into this
        per call by passing  `fetch=True` or toggle this setting to change the behavior
        globally.
        """,
    )

    runner_process_limit: int = Field(
        default=5,
        description="Maximum number of processes a runner will execute in parallel.",
    )

    runner_poll_frequency: int = Field(
        default=10,
        description="Number of seconds a runner should wait between queries for scheduled work.",
    )

    runner_server_missed_polls_tolerance: int = Field(
        default=2,
        description="Number of missed polls before a runner is considered unhealthy by its webserver.",
    )

    runner_server_host: str = Field(
        default="localhost",
        description="The host address the runner's webserver should bind to.",
    )

    runner_server_port: int = Field(
        default=8080,
        description="The port the runner's webserver should bind to.",
    )

    runner_server_log_level: LogLevel = Field(
        default="error",
        description="The log level of the runner's webserver.",
    )

    runner_server_enable: bool = Field(
        default=False,
        description="Whether or not to enable the runner's webserver.",
    )

    deployment_concurrency_slot_wait_seconds: float = Field(
        default=30.0,
        ge=0.0,
        description=(
            "The number of seconds to wait before retrying when a deployment flow run"
            " cannot secure a concurrency slot from the server."
        ),
    )

    deployment_schedule_max_scheduled_runs: int = Field(
        default=50,
        description="The maximum number of scheduled runs to create for a deployment.",
    )

    worker_heartbeat_seconds: float = Field(
        default=30,
        description="Number of seconds a worker should wait between sending a heartbeat.",
    )

    worker_query_seconds: float = Field(
        default=10,
        description="Number of seconds a worker should wait between queries for scheduled work.",
    )

    worker_prefetch_seconds: float = Field(
        default=10,
        description="The number of seconds into the future a worker should query for scheduled work.",
    )

    worker_webserver_host: str = Field(
        default="0.0.0.0",
        description="The host address the worker's webserver should bind to.",
    )

    worker_webserver_port: int = Field(
        default=8080,
        description="The port the worker's webserver should bind to.",
    )

    task_scheduling_default_storage_block: Optional[str] = Field(
        default=None,
        description="The `block-type/block-document` slug of a block to use as the default storage for autonomous tasks.",
    )

    task_scheduling_delete_failed_submissions: bool = Field(
        default=True,
        description="Whether or not to delete failed task submissions from the database.",
    )

    task_scheduling_max_scheduled_queue_size: int = Field(
        default=1000,
        description="The maximum number of scheduled tasks to queue for submission.",
    )

    task_scheduling_max_retry_queue_size: int = Field(
        default=100,
        description="The maximum number of retries to queue for submission.",
    )

    task_scheduling_pending_task_timeout: timedelta = Field(
        default=timedelta(0),
        description="How long before a PENDING task are made available to another task worker.",
    )

    experimental_enable_schedule_concurrency: bool = Field(
        default=False,
        description="Whether or not to enable concurrency for scheduled tasks.",
    )

    default_result_storage_block: Optional[str] = Field(
        default=None,
        description="The `block-type/block-document` slug of a block to use as the default result storage.",
    )

    default_work_pool_name: Optional[str] = Field(
        default=None,
        description="The default work pool to deploy to.",
    )

    default_docker_build_namespace: Optional[str] = Field(
        default=None,
        description="The default Docker namespace to use when building images.",
    )

    messaging_broker: str = Field(
        default="prefect.server.utilities.messaging.memory",
        description="Which message broker implementation to use for the messaging system, should point to a module that exports a Publisher and Consumer class.",
    )

    messaging_cache: str = Field(
        default="prefect.server.utilities.messaging.memory",
        description="Which cache implementation to use for the events system.  Should point to a module that exports a Cache class.",
    )

    ###########################################################################
    # allow deprecated access to PREFECT_SOME_SETTING_NAME

    def __getattribute__(self, name: str) -> Any:
        if name.startswith("PREFECT_"):
            field_name = env_var_to_attr_name(name)
            warnings.warn(
                f"Accessing `Settings().{name}` is deprecated. Use `Settings().{field_name}` instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return super().__getattribute__(field_name)
        return super().__getattribute__(name)

    ###########################################################################

    @model_validator(mode="after")
    def post_hoc_settings(self) -> Self:
        """refactor on resolution of https://github.com/pydantic/pydantic/issues/9789

        we should not be modifying __pydantic_fields_set__ directly, but until we can
        define dependencies between defaults in a first-class way, we need clean up
        post-hoc default assignments to keep set/unset fields correct after instantiation.
        """
        if self.cloud_ui_url is None:
            self.cloud_ui_url = default_cloud_ui_url(self)
            self.__pydantic_fields_set__.remove("cloud_ui_url")

        if self.ui_url is None:
            self.ui_url = default_ui_url(self)
            self.__pydantic_fields_set__.remove("ui_url")
        if self.ui_api_url is None:
            if self.api_url:
                self.ui_api_url = self.api_url
                self.__pydantic_fields_set__.remove("ui_api_url")
            else:
                self.ui_api_url = (
                    f"http://{self.server_api_host}:{self.server_api_port}"
                )
                self.__pydantic_fields_set__.remove("ui_api_url")
        if self.profiles_path is None or "PREFECT_HOME" in str(self.profiles_path):
            self.profiles_path = Path(f"{self.home}/profiles.toml")
            self.__pydantic_fields_set__.remove("profiles_path")
        if self.local_storage_path is None:
            self.local_storage_path = Path(f"{self.home}/storage")
            self.__pydantic_fields_set__.remove("local_storage_path")
        if self.memo_store_path is None:
            self.memo_store_path = Path(f"{self.home}/memo_store.toml")
            self.__pydantic_fields_set__.remove("memo_store_path")
        if self.debug_mode or self.test_mode:
            self.logging_level = "DEBUG"
            self.logging_internal_level = "DEBUG"
            self.__pydantic_fields_set__.remove("logging_level")
            self.__pydantic_fields_set__.remove("logging_internal_level")

        if self.logging_settings_path is None:
            self.logging_settings_path = Path(f"{self.home}/logging.yml")
            self.__pydantic_fields_set__.remove("logging_settings_path")
        # Set default database connection URL if not provided
        if self.api_database_connection_url is None:
            self.api_database_connection_url = default_database_connection_url(self)
            self.__pydantic_fields_set__.remove("api_database_connection_url")
        if "PREFECT_API_DATABASE_PASSWORD" in (
            db_url := (
                self.api_database_connection_url.get_secret_value()
                if isinstance(self.api_database_connection_url, SecretStr)
                else self.api_database_connection_url
            )
        ):
            if self.api_database_password is None:
                raise ValueError(
                    "database password is None - please set PREFECT_API_DATABASE_PASSWORD"
                )
            self.api_database_connection_url = SecretStr(
                db_url.replace(
                    "${PREFECT_API_DATABASE_PASSWORD}",
                    self.api_database_password.get_secret_value(),
                )
                if self.api_database_password
                else ""
            )
            self.__pydantic_fields_set__.remove("api_database_connection_url")
        return self

    @model_validator(mode="after")
    def emit_warnings(self):
        """More post-hoc validation of settings, including warnings for misconfigurations."""
        values = self.model_dump()
        values = max_log_size_smaller_than_batch_size(values)
        values = warn_on_database_password_value_without_usage(values)
        if not self.silence_api_url_misconfiguration:
            values = warn_on_misconfigured_api_url(values)
        return self

    ##########################################################################
    # Settings methods

    @classmethod
    def valid_setting_names(cls) -> Set[str]:
        """
        A set of valid setting names, e.g. "PREFECT_API_URL" or "PREFECT_API_KEY".
        """
        return set(
            f"{cls.model_config.get('env_prefix')}{key.upper()}"
            for key in cls.model_fields.keys()
        )

    def copy_with_update(
        self: Self,
        updates: Optional[Mapping[Setting, Any]] = None,
        set_defaults: Optional[Mapping[Setting, Any]] = None,
        restore_defaults: Optional[Iterable[Setting]] = None,
    ) -> Self:
        """
        Create a new Settings object with validation.

        Arguments:
            updates: A mapping of settings to new values. Existing values for the
                given settings will be overridden.
            set_defaults: A mapping of settings to new default values. Existing values for
                the given settings will only be overridden if they were not set.
            restore_defaults: An iterable of settings to restore to their default values.

        Returns:
            A new Settings object.
        """
        restore_defaults_names = set(r.field_name for r in restore_defaults or [])
        updates = updates or {}
        set_defaults = set_defaults or {}

        new_settings = self.__class__(
            **{setting.field_name: value for setting, value in set_defaults.items()}
            | self.model_dump(exclude_unset=True, exclude=restore_defaults_names)
            | {setting.field_name: value for setting, value in updates.items()}
        )
        return new_settings

    def hash_key(self) -> str:
        """
        Return a hash key for the settings object.  This is needed since some
        settings may be unhashable, like lists.
        """
        env_variables = self.to_environment_variables()
        return str(hash(tuple((key, value) for key, value in env_variables.items())))

    def to_environment_variables(
        self,
        include: Optional[Iterable[Setting]] = None,
        exclude: Optional[Iterable[Setting]] = None,
        exclude_unset: bool = False,
        include_secrets: bool = True,
    ) -> Dict[str, str]:
        """Convert the settings object to a dictionary of environment variables."""
        included_names = {s.field_name for s in include} if include else None
        excluded_names = {s.field_name for s in exclude} if exclude else None

        if exclude_unset:
            if included_names is None:
                included_names = set(self.model_dump(exclude_unset=True).keys())
            else:
                included_names.intersection_update(
                    {key for key in self.model_dump(exclude_unset=True)}
                )

        env: Dict[str, Any] = self.model_dump(
            include=included_names,
            exclude=excluded_names,
            mode="json",
            context={"include_secrets": include_secrets},
        )
        return {
            f"{self.model_config.get('env_prefix')}{key.upper()}": str(value)
            for key, value in env.items()
            if value is not None
        }

    @model_serializer(
        mode="wrap", when_used="always"
    )  # TODO: reconsider `when_used` default for more control
    def ser_model(
        self, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ) -> Any:
        ctx = info.context
        jsonable_self = handler(self)
        if ctx and ctx.get("include_secrets") is True:
            dump_kwargs = dict(include=info.include, exclude=info.exclude)
            jsonable_self.update(
                {
                    field_name: visit_collection(
                        expr=getattr(self, field_name),
                        visit_fn=partial(handle_secret_render, context=ctx),
                        return_data=True,
                    )
                    for field_name in set(self.model_dump(**dump_kwargs).keys())  # type: ignore
                }
            )
        return jsonable_self


############################################################################
# Settings utils

# Functions to instantiate `Settings` instances


def _cast_settings(
    settings: Union[Dict[Union[str, Setting], Any], Any],
) -> Dict[Setting, Any]:
    """For backwards compatibility, allow either Settings objects as keys or string references to settings."""
    if not isinstance(settings, dict):
        raise ValueError("Settings must be a dictionary.")
    casted_settings = {}
    for k, value in settings.items():
        try:
            if isinstance(k, str):
                field = Settings.model_fields[env_var_to_attr_name(k)]
                setting = Setting(
                    name=k,
                    default=field.default,
                    type_=field.annotation,
                )
            else:
                setting = k
            casted_settings[setting] = value
        except KeyError as e:
            warnings.warn(f"Setting {e} is not recognized")
            continue
    return casted_settings


def get_current_settings() -> Settings:
    """
    Returns a settings object populated with values from the current settings context
    or, if no settings context is active, the environment.
    """
    from prefect.context import SettingsContext

    settings_context = SettingsContext.get()
    if settings_context is not None:
        return settings_context.settings

    return Settings()


@contextmanager
def temporary_settings(
    updates: Optional[Mapping[Setting, Any]] = None,
    set_defaults: Optional[Mapping[Setting, Any]] = None,
    restore_defaults: Optional[Iterable[Setting]] = None,
) -> Generator[Settings, None, None]:
    """
    Temporarily override the current settings by entering a new profile.

    See `Settings.copy_with_update` for details on different argument behavior.

    Examples:
        >>> from prefect.settings import PREFECT_API_URL
        >>>
        >>> with temporary_settings(updates={PREFECT_API_URL: "foo"}):
        >>>    assert PREFECT_API_URL.value() == "foo"
        >>>
        >>>    with temporary_settings(set_defaults={PREFECT_API_URL: "bar"}):
        >>>         assert PREFECT_API_URL.value() == "foo"
        >>>
        >>>    with temporary_settings(restore_defaults={PREFECT_API_URL}):
        >>>         assert PREFECT_API_URL.value() is None
        >>>
        >>>         with temporary_settings(set_defaults={PREFECT_API_URL: "bar"})
        >>>             assert PREFECT_API_URL.value() == "bar"
        >>> assert PREFECT_API_URL.value() is None
    """
    import prefect.context

    context = prefect.context.get_settings_context()

    if not restore_defaults:
        restore_defaults = []

    new_settings = context.settings.copy_with_update(
        updates=updates, set_defaults=set_defaults, restore_defaults=restore_defaults
    )

    with prefect.context.SettingsContext(
        profile=context.profile, settings=new_settings
    ):
        yield new_settings


############################################################################
# Profiles


class Profile(BaseModel):
    """A user profile containing settings."""

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    name: str
    settings: Annotated[Dict[Setting, Any], BeforeValidator(_cast_settings)] = Field(
        default_factory=dict
    )
    source: Optional[Path] = None

    def to_environment_variables(self) -> Dict[str, str]:
        """Convert the profile settings to a dictionary of environment variables."""
        return {
            setting.name: str(value)
            for setting, value in self.settings.items()
            if value is not None
        }

    def validate_settings(self):
        errors: List[Tuple[Setting, ValidationError]] = []
        for setting, value in self.settings.items():
            try:
                TypeAdapter(
                    Settings.model_fields[setting.field_name].annotation
                ).validate_python(value)
            except ValidationError as e:
                errors.append((setting, e))
        if errors:
            raise ProfileSettingsValidationError(errors)


class ProfilesCollection:
    """ "
    A utility class for working with a collection of profiles.

    Profiles in the collection must have unique names.

    The collection may store the name of the active profile.
    """

    def __init__(
        self, profiles: Iterable[Profile], active: Optional[str] = None
    ) -> None:
        self.profiles_by_name = {profile.name: profile for profile in profiles}
        self.active_name = active

    @property
    def names(self) -> Set[str]:
        """
        Return a set of profile names in this collection.
        """
        return set(self.profiles_by_name.keys())

    @property
    def active_profile(self) -> Optional[Profile]:
        """
        Retrieve the active profile in this collection.
        """
        if self.active_name is None:
            return None
        return self[self.active_name]

    def set_active(self, name: Optional[str], check: bool = True):
        """
        Set the active profile name in the collection.

        A null value may be passed to indicate that this collection does not determine
        the active profile.
        """
        if check and name is not None and name not in self.names:
            raise ValueError(f"Unknown profile name {name!r}.")
        self.active_name = name

    def update_profile(
        self,
        name: str,
        settings: Dict[Setting, Any],
        source: Optional[Path] = None,
    ) -> Profile:
        """
        Add a profile to the collection or update the existing on if the name is already
        present in this collection.

        If updating an existing profile, the settings will be merged. Settings can
        be dropped from the existing profile by setting them to `None` in the new
        profile.

        Returns the new profile object.
        """
        existing = self.profiles_by_name.get(name)

        # Convert the input to a `Profile` to cast settings to the correct type
        profile = Profile(name=name, settings=settings, source=source)

        if existing:
            new_settings = {**existing.settings, **profile.settings}

            # Drop null keys to restore to default
            for key, value in tuple(new_settings.items()):
                if value is None:
                    new_settings.pop(key)

            new_profile = Profile(
                name=profile.name,
                settings=new_settings,
                source=source or profile.source,
            )
        else:
            new_profile = profile

        self.profiles_by_name[new_profile.name] = new_profile

        return new_profile

    def add_profile(self, profile: Profile) -> None:
        """
        Add a profile to the collection.

        If the profile name already exists, an exception will be raised.
        """
        if profile.name in self.profiles_by_name:
            raise ValueError(
                f"Profile name {profile.name!r} already exists in collection."
            )

        self.profiles_by_name[profile.name] = profile

    def remove_profile(self, name: str) -> None:
        """
        Remove a profile from the collection.
        """
        self.profiles_by_name.pop(name)

    def without_profile_source(self, path: Optional[Path]) -> "ProfilesCollection":
        """
        Remove profiles that were loaded from a given path.

        Returns a new collection.
        """
        return ProfilesCollection(
            [
                profile
                for profile in self.profiles_by_name.values()
                if profile.source != path
            ],
            active=self.active_name,
        )

    def to_dict(self):
        """
        Convert to a dictionary suitable for writing to disk.
        """
        return {
            "active": self.active_name,
            "profiles": {
                profile.name: profile.to_environment_variables()
                for profile in self.profiles_by_name.values()
            },
        }

    def __getitem__(self, name: str) -> Profile:
        return self.profiles_by_name[name]

    def __iter__(self):
        return self.profiles_by_name.__iter__()

    def items(self):
        return self.profiles_by_name.items()

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, ProfilesCollection):
            return False

        return (
            self.profiles_by_name == __o.profiles_by_name
            and self.active_name == __o.active_name
        )

    def __repr__(self) -> str:
        return (
            f"ProfilesCollection(profiles={list(self.profiles_by_name.values())!r},"
            f" active={self.active_name!r})>"
        )


def _read_profiles_from(path: Path) -> ProfilesCollection:
    """
    Read profiles from a path into a new `ProfilesCollection`.

    Profiles are expected to be written in TOML with the following schema:
        ```
        active = <name: Optional[str]>

        [profiles.<name: str>]
        <SETTING: str> = <value: Any>
        ```
    """
    contents = toml.loads(path.read_text())
    active_profile = contents.get("active")
    raw_profiles = contents.get("profiles", {})

    profiles = []
    for name, settings in raw_profiles.items():
        profiles.append(Profile(name=name, settings=settings, source=path))

    return ProfilesCollection(profiles, active=active_profile)


def _write_profiles_to(path: Path, profiles: ProfilesCollection) -> None:
    """
    Write profiles in the given collection to a path as TOML.

    Any existing data not present in the given `profiles` will be deleted.
    """
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(mode=0o600)
    path.write_text(toml.dumps(profiles.to_dict()))


def load_profiles(include_defaults: bool = True) -> ProfilesCollection:
    """
    Load profiles from the current profile path. Optionally include profiles from the
    default profile path.
    """
    current_settings = get_current_settings()
    default_profiles = _read_profiles_from(DEFAULT_PROFILES_PATH)

    if current_settings.profiles_path is None:
        raise RuntimeError(
            "No profiles path set; please ensure `PREFECT_PROFILES_PATH` is set."
        )

    if not include_defaults:
        if not current_settings.profiles_path.exists():
            return ProfilesCollection([])
        return _read_profiles_from(current_settings.profiles_path)

    user_profiles_path = current_settings.profiles_path
    profiles = default_profiles
    if user_profiles_path.exists():
        user_profiles = _read_profiles_from(user_profiles_path)

        # Merge all of the user profiles with the defaults
        for name in user_profiles:
            if not (source := user_profiles[name].source):
                raise ValueError(f"Profile {name!r} has no source.")
            profiles.update_profile(
                name,
                settings=user_profiles[name].settings,
                source=source,
            )

        if user_profiles.active_name:
            profiles.set_active(user_profiles.active_name, check=False)

    return profiles


def load_current_profile():
    """
    Load the current profile from the default and current profile paths.

    This will _not_ include settings from the current settings context. Only settings
    that have been persisted to the profiles file will be saved.
    """
    import prefect.context

    profiles = load_profiles()
    context = prefect.context.get_settings_context()

    if context:
        profiles.set_active(context.profile.name)

    return profiles.active_profile


def save_profiles(profiles: ProfilesCollection) -> None:
    """
    Writes all non-default profiles to the current profiles path.
    """
    profiles_path = get_current_settings().profiles_path
    assert profiles_path is not None, "Profiles path is not set."
    profiles = profiles.without_profile_source(DEFAULT_PROFILES_PATH)
    return _write_profiles_to(profiles_path, profiles)


def load_profile(name: str) -> Profile:
    """
    Load a single profile by name.
    """
    profiles = load_profiles()
    try:
        return profiles[name]
    except KeyError:
        raise ValueError(f"Profile {name!r} not found.")


def update_current_profile(
    settings: Dict[Union[str, Setting], Any],
) -> Profile:
    """
    Update the persisted data for the profile currently in-use.

    If the profile does not exist in the profiles file, it will be created.

    Given settings will be merged with the existing settings as described in
    `ProfilesCollection.update_profile`.

    Returns:
        The new profile.
    """
    import prefect.context

    current_profile = prefect.context.get_settings_context().profile

    if not current_profile:
        from prefect.exceptions import MissingProfileError

        raise MissingProfileError("No profile is currently in use.")

    profiles = load_profiles()

    # Ensure the current profile's settings are present
    profiles.update_profile(current_profile.name, current_profile.settings)
    # Then merge the new settings in
    new_profile = profiles.update_profile(
        current_profile.name, _cast_settings(settings)
    )

    new_profile.validate_settings()

    save_profiles(profiles)

    return profiles[current_profile.name]


############################################################################
# Allow traditional env var access


class _SettingsDict(dict):
    """allow either `field_name` or `ENV_VAR_NAME` access
    ```
    d = _SettingsDict(Settings)
    d["api_url"] == d["PREFECT_API_URL"]
    ```
    """

    def __init__(self: Self, settings_cls: Type[BaseSettings]):
        super().__init__()
        for field_name, field in settings_cls.model_fields.items():
            setting = Setting(
                name=f"{settings_cls.model_config.get('env_prefix')}{field_name.upper()}",
                default=field.default,
                type_=field.annotation,
            )
            self[field_name] = self[setting.name] = setting


SETTING_VARIABLES: dict[str, Setting] = _SettingsDict(Settings)


def __getattr__(name: str) -> Setting:
    if name in Settings.valid_setting_names():
        return SETTING_VARIABLES[name]
    raise AttributeError(f"{name} is not a Prefect setting.")


__all__ = [  # noqa: F822
    "Profile",
    "ProfilesCollection",
    "Setting",
    "Settings",
    "load_current_profile",
    "update_current_profile",
    "load_profile",
    "save_profiles",
    "load_profiles",
    "get_current_settings",
    "temporary_settings",
    "DEFAULT_PROFILES_PATH",
    # add public settings here for auto-completion
    "PREFECT_API_KEY",  # type: ignore
    "PREFECT_API_URL",  # type: ignore
    "PREFECT_UI_URL",  # type: ignore
]
