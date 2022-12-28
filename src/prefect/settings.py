"""
Prefect settings management.

Each setting is defined as a `Setting` type. The name of each setting is stylized in all
caps, matching the environment variable that can be used to change the setting.

All settings defined in this file are used to generate a dynamic Pydantic settings class
called `Settings`. When insantiated, this class will load settings from environment
variables and pull default values from the setting definitions.

The current instance of `Settings` being used by the application is stored in a
`SettingsContext` model which allows each instance of the `Settings` class to be
accessed in an async-safe manner.

Aside from environment variables, we allow settings to be changed during the runtime of
the process using profiles. Profiles contain setting overrides that the user may
persist without setting environment variables. Profiles are also used internally for
managing settings during task run execution where differing settings may be used
concurrently in the same process and during testing where we need to override settings
to ensure their value is respected as intended.

The `SettingsContext` is set when the `prefect` module is imported. This context is
referred to as the "root" settings context for clarity. Generally, this is the only
settings context that will be used. When this context is entered, we will instantiate
a `Settings` object, loading settings from environment variables and defaults, then we
will load the active profile and use it to override settings. See  `enter_root_settings_context`
for details on determining the active profile.

Another `SettingsContext` may be entered at any time to change the settings being
used by the code within the context. Generally, users should not use this. Settings
management should be left to Prefect application internals.

Generally, settings should be accessed with `SETTING_VARIABLE.value()` which will
pull the current `Settings` instance from the current `SettingsContext` and retrieve
the value of the relevant setting.

Accessing a setting's value will also call the `Setting.value_callback` which allows
settings to be dynamically modified on retrieval. This allows us to make settings
dependent on the value of other settings or perform other dynamic effects.

"""
import logging
import os
import string
import warnings
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
)

import pydantic
import toml
from pydantic import BaseSettings, Field, create_model, root_validator, validator

from prefect.exceptions import MissingProfileError
from prefect.utilities.names import OBFUSCATED_PREFIX, obfuscate
from prefect.utilities.pydantic import add_cloudpickle_reduction

T = TypeVar("T")


DEFAULT_PROFILES_PATH = Path(__file__).parent.joinpath("profiles.toml")


class Setting(Generic[T]):
    """
    Setting definition type.
    """

    def __init__(
        self,
        type: Type[T],
        *,
        value_callback: Callable[["Settings", T], T] = None,
        is_secret: bool = False,
        **kwargs,
    ) -> None:
        self.field: pydantic.fields.FieldInfo = Field(**kwargs)
        self.type = type
        self.value_callback = value_callback
        self.name = None  # Will be populated after all settings are defined
        self.is_secret = is_secret

        self.__doc__ = self.field.description

    def value(self, bypass_callback: bool = False) -> T:
        """
        Get the current value of a setting.

        Example:
        ```python
        from prefect.settings import PREFECT_API_URL
        PREFECT_API_URL.value()
        ```
        """
        return self.value_from(get_current_settings(), bypass_callback=bypass_callback)

    def value_from(self, settings: "Settings", bypass_callback: bool = False) -> T:
        """
        Get the value of a setting from a settings object

        Example:
        ```python
        from prefect.settings import get_default_settings
        PREFECT_API_URL.value_from(get_default_settings())
        ```
        """
        return settings.value_of(self, bypass_callback=bypass_callback)

    def __repr__(self) -> str:
        return f"<{self.name}: {self.type.__name__}>"

    def __bool__(self) -> bool:
        """
        Returns a truthy check of the current value.
        """
        return bool(self.value())

    def __eq__(self, __o: object) -> bool:
        return __o.__eq__(self.value())

    def __hash__(self) -> int:
        return hash((type(self), self.name))


# Callbacks and validators


def get_extra_loggers(_: "Settings", value: str) -> List[str]:
    """
    `value_callback` for `PREFECT_LOGGING_EXTRA_LOGGERS`that parses the CSV string into a
    list and trims whitespace from logger names.
    """
    return [name.strip() for name in value.split(",")] if value else []


def expanduser_in_path(_, value: Path) -> Path:
    return value.expanduser()


def debug_mode_log_level(settings, value):
    """
    `value_callback` for `PREFECT_LOGGING_LEVEL` that overrides the log level to DEBUG
    when debug mode is enabled.
    """
    if PREFECT_DEBUG_MODE.value_from(settings):
        return "DEBUG"
    else:
        return value


def only_return_value_in_test_mode(settings, value):
    """
    `value_callback` for `PREFECT_TEST_SETTING` that only allows access during test mode
    """
    if PREFECT_TEST_MODE.value_from(settings):
        return value
    else:
        return None


def default_ui_api_url(settings, value):
    """
    `value_callback` for `PREFECT_ORION_UI_API_URL` that sets the default value to
    `PREFECT_API_URL` if set otherwise it constructs an API URL from the API settings.
    """
    if value is None:
        # Set a default value
        if PREFECT_API_URL.value_from(settings):
            value = "${PREFECT_API_URL}"
        else:
            value = "http://${PREFECT_ORION_API_HOST}:${PREFECT_ORION_API_PORT}/api"

    return template_with_settings(
        PREFECT_ORION_API_HOST, PREFECT_ORION_API_PORT, PREFECT_API_URL
    )(settings, value)


def template_with_settings(*upstream_settings: Setting) -> Callable[["Settings", T], T]:
    """
    Returns a `value_callback` that will template the given settings into the runtime
    value for the setting.
    """

    def templater(settings, value):
        original_type = type(value)
        template_values = {
            setting.name: setting.value_from(settings) for setting in upstream_settings
        }
        template = string.Template(str(value))
        return original_type(template.substitute(template_values))

    return templater


def max_log_size_smaller_than_batch_size(values):
    """
    Validator for settings asserting the batch size and match log size are compatible
    """
    if (
        values["PREFECT_LOGGING_ORION_BATCH_SIZE"]
        < values["PREFECT_LOGGING_ORION_MAX_LOG_SIZE"]
    ):
        raise ValueError(
            "`PREFECT_LOGGING_ORION_MAX_LOG_SIZE` cannot be larger than `PREFECT_LOGGING_ORION_BATCH_SIZE`"
        )
    return values


def warn_on_database_password_value_without_usage(values):
    """
    Validator for settings warning if the database password is set but not used.
    """
    value = values["PREFECT_ORION_DATABASE_PASSWORD"]
    if (
        value
        and not value.startswith(OBFUSCATED_PREFIX)
        and (
            "PREFECT_ORION_DATABASE_PASSWORD"
            not in values["PREFECT_ORION_DATABASE_CONNECTION_URL"]
        )
    ):
        warnings.warn(
            "PREFECT_ORION_DATABASE_PASSWORD is set but not included in the "
            "PREFECT_ORION_DATABASE_CONNECTION_URL. "
            "The provided password will be ignored."
        )
    return values


def get_deprecated_prefect_cloud_url(settings, value):
    warnings.warn(
        "`PREFECT_CLOUD_URL` is deprecated. Use `PREFECT_CLOUD_API_URL` instead.",
        DeprecationWarning,
    )
    return value or PREFECT_CLOUD_API_URL.value_from(settings)


def check_for_deprecated_cloud_url(settings, value):
    deprecated_value = PREFECT_CLOUD_URL.value_from(settings, bypass_callback=True)
    if deprecated_value is not None:
        warnings.warn(
            "`PREFECT_CLOUD_URL` is set and will be used instead of `PREFECT_CLOUD_API_URL` for backwards compatibility. `PREFECT_CLOUD_URL` is deprecated, set `PREFECT_CLOUD_API_URL` instead.",
            DeprecationWarning,
        )
    return deprecated_value or value


def default_ui_url(settings, value):
    if value is not None:
        return value

    # Otherwise, infer a value from the API URL
    ui_url = api_url = PREFECT_API_URL.value_from(settings)

    if not api_url:
        return None

    cloud_url = PREFECT_CLOUD_API_URL.value_from(settings)
    cloud_ui_url = PREFECT_CLOUD_UI_URL.value_from(settings)
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


def default_cloud_ui_url(settings, value):
    if value is not None:
        return value

    # Otherwise, infer a value from the API URL
    ui_url = api_url = PREFECT_CLOUD_API_URL.value_from(settings)

    if api_url.startswith("https://api.prefect.cloud"):
        ui_url = ui_url.replace(
            "https://api.prefect.cloud", "https://app.prefect.cloud", 1
        )

    if ui_url.endswith("/api"):
        ui_url = ui_url[:-4]

    return ui_url


# Setting definitions


PREFECT_HOME = Setting(
    Path,
    default=Path("~") / ".prefect",
    value_callback=expanduser_in_path,
)
"""Prefect's home directory. Defaults to `~/.prefect`. This
directory may be created automatically when required.
"""

PREFECT_EXTRA_ENTRYPOINTS = Setting(
    str,
    default="",
)
"""
Modules for Prefect to import when Prefect is imported.

Values should be separated by commas, e.g. `my_module,my_other_module`.
Objects within modules may be specified by a ':' partition, e.g. `my_module:my_object`.
If a callable object is provided, it will be called with no arguments on import.
"""

PREFECT_DEBUG_MODE = Setting(
    bool,
    default=False,
)
"""If `True`, places the API in debug mode. This may modify
behavior to facilitate debugging, including extra logs and other verbose
assistance. Defaults to `False`.
"""

PREFECT_CLI_COLORS = Setting(
    bool,
    default=True,
)
"""If `True`, use colors in CLI output. If `False`,
output will not include colors codes. Defaults to `True`.
"""

PREFECT_CLI_WRAP_LINES = Setting(
    bool,
    default=True,
)
"""If `True`, wrap text by inserting new lines in long lines
in CLI output. If `False`, output will not be wrapped. Defaults to `True`.
"""

PREFECT_TEST_MODE = Setting(
    bool,
    default=False,
)
"""If `True`, places the API in test mode. This may modify
behavior to faciliate testing. Defaults to `False`.
"""

PREFECT_TEST_SETTING = Setting(
    Any,
    default=None,
    value_callback=only_return_value_in_test_mode,
)
"""
This variable only exists to faciliate testing of settings.
If accessed when `PREFECT_TEST_MODE` is not set, `None` is returned.
"""

PREFECT_API_URL = Setting(
    str,
    default=None,
)
"""
If provided, the url of an externally-hosted Orion API. Defaults to `None`.

When using Prefect Cloud, this will include an account and workspace.
"""

PREFECT_API_KEY = Setting(
    str,
    default=None,
    is_secret=True,
)
"""API key used to authenticate against Orion API. Defaults to `None`."""

PREFECT_API_ENABLE_HTTP2 = Setting(bool, default=True)
"""If True, enable support for HTTP/2 for communicating with a remote Orion API.

If the remote Orion API does not support HTTP/2, this will have no effect and
connections will be made via HTTP/1.1"""

PREFECT_CLOUD_API_URL = Setting(
    str,
    default="https://api.prefect.cloud/api",
    value_callback=check_for_deprecated_cloud_url,
)
"""API URL for Prefect Cloud. Used for authentication."""


PREFECT_CLOUD_URL = Setting(
    str, default=None, value_callback=get_deprecated_prefect_cloud_url
)
"""
DEPRECATED: Use `PREFECT_CLOUD_API_URL` instead.
"""

PREFECT_UI_URL = Setting(
    Optional[str],
    default=None,
    value_callback=default_ui_url,
)
"""
The URL for the UI. By default, this is inferred from the PREFECT_API_URL.

When using Prefect Cloud, this will include the account and workspace.
When using an ephemeral server, this will be `None`.
"""


PREFECT_CLOUD_UI_URL = Setting(
    str,
    default=None,
    value_callback=default_cloud_ui_url,
)
"""
The URL for the Cloud UI. By default, this is inferred from the PREFECT_CLOUD_API_URL.

Note: PREFECT_UI_URL will be workspace specific and will be usable in the open source too.
      In contrast, this value is only valid for Cloud and will not include the workspace.
"""

PREFECT_API_REQUEST_TIMEOUT = Setting(
    float,
    default=30.0,
)
"""The default timeout for requests to the API"""

PREFECT_EXPERIMENTAL_WARN = Setting(bool, default=True)
"""
If enabled, warn on usage of expirimental features.
"""

PREFECT_PROFILES_PATH = Setting(
    Path,
    default=Path("${PREFECT_HOME}") / "profiles.toml",
    value_callback=template_with_settings(PREFECT_HOME),
)
"""The path to a profiles configuration files."""

PREFECT_RESULTS_DEFAULT_SERIALIZER = Setting(
    str,
    default="pickle",
)
"""The default serializer to use when not otherwise specified."""


PREFECT_RESULTS_PERSIST_BY_DEFAULT = Setting(
    bool,
    default=False,
)
"""
The default setting for persisting results when not otherwise specified. If enabled,
flow and task results will be persisted unless they opt out.
"""


PREFECT_LOCAL_STORAGE_PATH = Setting(
    Path,
    default=Path("${PREFECT_HOME}") / "storage",
    value_callback=template_with_settings(PREFECT_HOME),
)
"""The path to a directory to store things in."""

PREFECT_MEMO_STORE_PATH = Setting(
    Path,
    default=Path("${PREFECT_HOME}") / "memo_store.toml",
    value_callback=template_with_settings(PREFECT_HOME),
)
"""The path to the memo store file."""

PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION = Setting(
    bool,
    default=True,
)
"""
Controls whether or not block auto-registration on start 
up should be memoized. Setting to False may result in slower server start
up times.
"""

PREFECT_LOGGING_LEVEL = Setting(
    str,
    default="INFO",
    value_callback=debug_mode_log_level,
)
"""
The default logging level for Prefect loggers. Defaults to
"INFO" during normal operation. Is forced to "DEBUG" during debug mode.
"""

PREFECT_LOGGING_SERVER_LEVEL = Setting(
    str,
    default="WARNING",
)
"""The default logging level for the Orion API."""

PREFECT_LOGGING_SETTINGS_PATH = Setting(
    Path,
    default=Path("${PREFECT_HOME}") / "logging.yml",
    value_callback=template_with_settings(PREFECT_HOME),
)
"""
The path to a custom YAML logging configuration file. If
no file is found, the default `logging.yml` is used. 
Defaults to a logging.yml in the Prefect home directory.
"""

PREFECT_LOGGING_EXTRA_LOGGERS = Setting(
    str,
    default="",
    value_callback=get_extra_loggers,
)
"""
Additional loggers to attach to Prefect logging at runtime.
Values should be comma separated. The handlers attached to the 'prefect' logger
will be added to these loggers. Additionally, if the level is not set, it will
be set to the same level as the 'prefect' logger.
"""

PREFECT_LOGGING_LOG_PRINTS = Setting(
    bool,
    default=False,
)
"""
If set, `print` statements in flows and tasks will be redirected to the Prefect logger
for the given run. This setting can be overriden by individual tasks and flows.
"""

PREFECT_LOGGING_ORION_ENABLED = Setting(
    bool,
    default=True,
)
"""Should logs be sent to Orion? If False, logs sent to the `OrionHandler` will not be sent to the API."""

PREFECT_LOGGING_ORION_BATCH_INTERVAL = Setting(
    float,
    default=2.0,
)
"""The number of seconds between batched writes of logs to Orion."""

PREFECT_LOGGING_ORION_BATCH_SIZE = Setting(
    int,
    default=4_000_000,
)
"""The maximum size in bytes for a batch of logs."""

PREFECT_LOGGING_ORION_MAX_LOG_SIZE = Setting(
    int,
    default=1_000_000,
)
"""The maximum size in bytes for a single log."""

PREFECT_LOGGING_COLORS = Setting(
    bool,
    default=True,
)
"""Whether to style console logs with color."""

PREFECT_LOGGING_MARKUP = Setting(
    bool,
    default=False,
)
"""
Whether to interpret strings wrapped in square brackets as a style.
This allows styles to be conveniently added to log messages, e.g.
`[red]This is a red message.[/red]`. However, the downside is,
if enabled, strings that contain square brackets may be inaccurately
interpreted and lead to incomplete output, e.g.
`DROP TABLE [dbo].[SomeTable];"` outputs `DROP TABLE .[SomeTable];`.
"""

PREFECT_AGENT_QUERY_INTERVAL = Setting(
    float,
    default=10,
)
"""
The agent loop interval, in seconds. Agents will check for new runs this often. 
Defaults to `10`.
"""

PREFECT_AGENT_PREFETCH_SECONDS = Setting(
    int,
    default=10,
)
"""
Agents will look for scheduled runs this many seconds in
the future and attempt to run them. This accounts for any additional
infrastructure spin-up time or latency in preparing a flow run. Note
flow runs will not start before their scheduled time, even if they are
prefetched. Defaults to `10`.
"""

PREFECT_ASYNC_FETCH_STATE_RESULT = Setting(bool, default=False)
"""
Determines whether `State.result()` fetches results automatically or not.
In Prefect 2.6.0, the `State.result()` method was updated to be async
to faciliate automatic retrieval of results from storage which means when 
writing async code you must `await` the call. For backwards compatibility, 
the result is not retrieved by default for async users. You may opt into this
per call by passing  `fetch=True` or toggle this setting to change the behavior
globally.
This setting does not affect users writing synchronous tasks and flows.
This setting does not affect retrieval of results when using `Future.result()`.
"""

PREFECT_ORION_BLOCKS_REGISTER_ON_START = Setting(
    bool,
    default=True,
)
"""
If set, any block types that have been imported will be registered with the 
backend on application startup. If not set, block types must be manually 
registered.
"""

PREFECT_ORION_DATABASE_PASSWORD = Setting(
    str,
    default=None,
    is_secret=True,
)
"""
Password to template into the `PREFECT_ORION_DATABASE_CONNECTION_URL`.
This is useful if the password must be provided separately from the connection URL.
To use this setting, you must include it in your connection URL.
"""

PREFECT_ORION_DATABASE_CONNECTION_URL = Setting(
    str,
    default="sqlite+aiosqlite:///" + str(Path("${PREFECT_HOME}") / "orion.db"),
    value_callback=template_with_settings(
        PREFECT_HOME, PREFECT_ORION_DATABASE_PASSWORD
    ),
    is_secret=True,
)
"""
A database connection URL in a SQLAlchemy-compatible
format. Orion currently supports SQLite and Postgres. Note that all
Orion engines must use an async driver - for SQLite, use
`sqlite+aiosqlite` and for Postgres use `postgresql+asyncpg`.

SQLite in-memory databases can be used by providing the url
`sqlite+aiosqlite:///file::memory:?cache=shared&uri=true&check_same_thread=false`,
which will allow the database to be accessed by multiple threads. Note
that in-memory databases can not be accessed from multiple processes and
should only be used for simple tests.

Defaults to a sqlite database stored in the Prefect home directory.

If you need to provide password via a different environment variable, you use
the `PREFECT_ORION_DATABASE_PASSWORD` setting. For example:

```
PREFECT_ORION_DATABASE_PASSWORD='mypassword'
PREFECT_ORION_DATABASE_CONNECTION_URL='postgresql+asyncpg://postgres:${PREFECT_ORION_DATABASE_PASSWORD}@localhost/orion'
```
"""

PREFECT_ORION_DATABASE_ECHO = Setting(
    bool,
    default=False,
)
"""If `True`, SQLAlchemy will log all SQL issued to the database. Defaults to `False`."""

PREFECT_ORION_DATABASE_MIGRATE_ON_START = Setting(
    bool,
    default=True,
)
"""If `True`, the database will be upgraded on application creation. If `False`, the database will need to be upgraded manually."""

PREFECT_ORION_DATABASE_TIMEOUT = Setting(
    Optional[float],
    default=10.0,
)
"""
A statement timeout, in seconds, applied to all database interactions made by the API.
Defaults to 10 seconds.
"""

PREFECT_ORION_DATABASE_CONNECTION_TIMEOUT = Setting(
    Optional[float],
    default=5,
)
"""A connection timeout, in seconds, applied to database
connections. Defaults to `5`.
"""

PREFECT_ORION_SERVICES_SCHEDULER_LOOP_SECONDS = Setting(
    float,
    default=60,
)
"""The scheduler loop interval, in seconds. This determines
how often the scheduler will attempt to schedule new flow runs, but has no
impact on how quickly either flow runs or task runs are actually executed.
Defaults to `60`.
"""

PREFECT_ORION_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE = Setting(
    int,
    default=100,
)
"""The number of deployments the scheduler will attempt to
schedule in a single batch. If there are more deployments than the batch
size, the scheduler immediately attempts to schedule the next batch; it
does not sleep for `scheduler_loop_seconds` until it has visited every
deployment once. Defaults to `100`.
"""

PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS = Setting(
    int,
    default=100,
)
"""The scheduler will attempt to schedule up to this many
auto-scheduled runs in the future. Note that runs may have fewer than
this many scheduled runs, depending on the value of
`scheduler_max_scheduled_time`.  Defaults to `100`.
"""

PREFECT_ORION_SERVICES_SCHEDULER_MIN_RUNS = Setting(
    int,
    default=3,
)
"""The scheduler will attempt to schedule at least this many
auto-scheduled runs in the future. Note that runs may have more than
this many scheduled runs, depending on the value of
`scheduler_min_scheduled_time`.  Defaults to `3`.
"""

PREFECT_ORION_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME = Setting(
    timedelta,
    default=timedelta(days=100),
)
"""The scheduler will create new runs up to this far in the
future. Note that this setting will take precedence over
`scheduler_max_runs`: if a flow runs once a month and
`scheduler_max_scheduled_time` is three months, then only three runs will be
scheduled. Defaults to 100 days (`8640000` seconds).
"""

PREFECT_ORION_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME = Setting(
    timedelta,
    default=timedelta(hours=1),
)
"""The scheduler will create new runs at least this far in the
future. Note that this setting will take precedence over `scheduler_min_runs`:
if a flow runs every hour and `scheduler_min_scheduled_time` is three hours,
then three runs will be scheduled even if `scheduler_min_runs` is 1. Defaults to
1 hour (`3600` seconds).
"""

PREFECT_ORION_SERVICES_SCHEDULER_INSERT_BATCH_SIZE = Setting(
    int,
    default=500,
)
"""The number of flow runs the scheduler will attempt to insert
in one batch across all deployments. If the number of flow runs to
schedule exceeds this amount, the runs will be inserted in batches of this size. 
Defaults to `500`.
"""

PREFECT_ORION_SERVICES_LATE_RUNS_LOOP_SECONDS = Setting(
    float,
    default=5,
)
"""The late runs service will look for runs to mark as late
this often. Defaults to `5`.
"""

PREFECT_ORION_SERVICES_LATE_RUNS_AFTER_SECONDS = Setting(
    timedelta,
    default=timedelta(seconds=5),
)
"""The late runs service will mark runs as late after they
have exceeded their scheduled start time by this many seconds. Defaults
to `5` seconds.
"""

PREFECT_ORION_SERVICES_PAUSE_EXPIRATIONS_LOOP_SECONDS = Setting(
    float,
    default=5,
)
"""The pause expiration service will look for runs to mark as failed
this often. Defaults to `5`.
"""

PREFECT_ORION_API_DEFAULT_LIMIT = Setting(
    int,
    default=200,
)
"""The default limit applied to queries that can return
multiple objects, such as `POST /flow_runs/filter`.
"""

PREFECT_ORION_API_HOST = Setting(
    str,
    default="127.0.0.1",
)
"""The API's host address (defaults to `127.0.0.1`)."""

PREFECT_ORION_API_PORT = Setting(
    int,
    default=4200,
)
"""The API's port address (defaults to `4200`)."""

PREFECT_ORION_UI_ENABLED = Setting(
    bool,
    default=True,
)
"""Whether or not to serve the Orion UI."""

PREFECT_ORION_UI_API_URL = Setting(
    str,
    default=None,
    value_callback=default_ui_api_url,
)
"""The connection url for communication from the UI to the API.
Defaults to `PREFECT_API_URL` if set. Otherwise, the default URL is generated from
`PREFECT_ORION_API_HOST` and `PREFECT_ORION_API_PORT`. If providing a custom value,
the aforementioned settings may be templated into the given string.
"""

PREFECT_ORION_ANALYTICS_ENABLED = Setting(
    bool,
    default=True,
)
"""If True, Orion sends anonymous data (e.g. count of flow runs, package version) to Prefect to help us improve."""

PREFECT_ORION_SERVICES_SCHEDULER_ENABLED = Setting(
    bool,
    default=True,
)
"""Whether or not to start the scheduling service in the Orion application. 
If disabled, you will need to run this service separately to schedule runs for deployments.
"""

PREFECT_ORION_SERVICES_LATE_RUNS_ENABLED = Setting(
    bool,
    default=True,
)
"""Whether or not to start the late runs service in the Orion application. 
If disabled, you will need to run this service separately to have runs past their 
scheduled start time marked as late.
"""

PREFECT_ORION_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED = Setting(
    bool,
    default=True,
)
"""Whether or not to start the flow run notifications service in the Orion application. 
If disabled, you will need to run this service separately to send flow run notifications.
"""

PREFECT_ORION_SERVICES_PAUSE_EXPIRATIONS_ENABLED = Setting(
    bool,
    default=True,
)
"""Whether or not to start the paused flow run expiration service in the Orion
application. If disabled, paused flows that have timed out will remain in a Paused state
until a resume attempt.
"""

PREFECT_EXPERIMENTAL_ENABLE_WORKERS = Setting(bool, default=False)
"""
Whether or not to enable experimental Prefect workers. 
"""

# Collect all defined settings

SETTING_VARIABLES = {
    name: val for name, val in tuple(globals().items()) if isinstance(val, Setting)
}

# Populate names in settings objects from assignments above
# Uses `__` to avoid setting these as global variables which can lead to sneaky bugs

for __name, __setting in SETTING_VARIABLES.items():
    __setting.name = __name

# Dynamically create a pydantic model that includes all of our settings

SettingsFieldsMixin = create_model(
    "SettingsFieldsMixin",
    # Inheriting from `BaseSettings` provides environment variable loading
    __base__=BaseSettings,
    **{
        setting.name: (setting.type, setting.field)
        for setting in SETTING_VARIABLES.values()
    },
)


# Defining a class after this that inherits the dynamic class rather than setting
# __base__ to the following class ensures that mkdocstrings properly generates
# reference documentation. It does not support module-level variables, even if they are
# an object which has __doc__ set.


@add_cloudpickle_reduction
class Settings(SettingsFieldsMixin):
    """
    Contains validated Prefect settings.

    Settings should be accessed using the relevant `Setting` object. For example:
    ```python
    from prefect.settings import PREFECT_HOME
    PREFECT_HOME.value()
    ```

    Accessing a setting attribute directly will ignore any `value_callback` mutations.
    This is not recommended:
    ```python
    from prefect.settings import Settings
    Settings().PREFECT_PROFILES_PATH  # PosixPath('${PREFECT_HOME}/profiles.toml')
    ```
    """

    def value_of(self, setting: Setting[T], bypass_callback: bool = False) -> T:
        """
        Retrieve a setting's value.
        """
        value = getattr(self, setting.name)
        if setting.value_callback and not bypass_callback:
            value = setting.value_callback(self, value)
        return value

    @validator(PREFECT_LOGGING_LEVEL.name, PREFECT_LOGGING_SERVER_LEVEL.name)
    def check_valid_log_level(cls, value):
        if isinstance(value, str):
            value = value.upper()
        logging._checkLevel(value)
        return value

    @root_validator
    def post_root_validators(cls, values):
        """
        Add root validation functions for settings here.
        """
        # TODO: We could probably register these dynamically but this is the simpler
        #       approach for now. We can explore more interesting validation features
        #       in the future.
        values = max_log_size_smaller_than_batch_size(values)
        values = warn_on_database_password_value_without_usage(values)
        return values

    def copy_with_update(
        self,
        updates: Mapping[Setting, Any] = None,
        set_defaults: Mapping[Setting, Any] = None,
        restore_defaults: Iterable[Setting] = None,
    ) -> "Settings":
        """
        Create a new `Settings` object with validation.

        Arguments:
            updates: A mapping of settings to new values. Existing values for the
                given settings will be overridden.
            set_defaults: A mapping of settings to new default values. Existing values for
                the given settings will only be overridden if they were not set.
            restore_defaults: An iterable of settings to restore to their default values.

        Returns:
            A new `Settings` object.
        """
        updates = updates or {}
        set_defaults = set_defaults or {}
        restore_defaults = restore_defaults or set()
        restore_defaults_names = {setting.name for setting in restore_defaults}

        return self.__class__(
            **{
                **{setting.name: value for setting, value in set_defaults.items()},
                **self.dict(exclude_unset=True, exclude=restore_defaults_names),
                **{setting.name: value for setting, value in updates.items()},
            }
        )

    def with_obfuscated_secrets(self):
        """
        Returns a copy of this settings object with secret setting values obfuscated.
        """
        settings = self.copy(
            update={
                setting.name: obfuscate(self.value_of(setting))
                for setting in SETTING_VARIABLES.values()
                if setting.is_secret
            }
        )
        # Ensure that settings that have not been marked as "set" before are still so
        # after we have updated their value above
        settings.__fields_set__.intersection_update(self.__fields_set__)
        return settings

    def to_environment_variables(
        self, include: Iterable[Setting] = None, exclude_unset: bool = False
    ) -> Dict[str, str]:
        """
        Convert the settings object to environment variables.

        Note that setting values will not be run through their `value_callback` allowing
        dynamic resolution to occur when loaded from the returned environment.

        Args:
            include_keys: An iterable of settings to include in the return value.
                If not set, all settings are used.
            exclude_unset: Only include settings that have been set (i.e. the value is
                not from the default). If set, unset keys will be dropped even if they
                are set in `include_keys`.

        Returns:
            A dictionary of settings with values cast to strings
        """
        include = set(include or SETTING_VARIABLES.values())

        if exclude_unset:
            set_keys = {
                # Collect all of the "set" keys and cast to `Setting` objects
                SETTING_VARIABLES[key]
                for key in self.dict(exclude_unset=True)
            }
            include.intersection_update(set_keys)

        # Validate the types of items in `include` to prevent exclusion bugs
        for key in include:
            if not isinstance(key, Setting):
                raise TypeError(
                    "Invalid type {type(key).__name__!r} for key in `include`."
                )

        env = {
            # Use `getattr` instead of `value_of` to avoid value callback resolution
            key: getattr(self, key)
            for key, setting in SETTING_VARIABLES.items()
            if setting in include
        }

        # Cast to strings and drop null values
        return {key: str(value) for key, value in env.items() if value is not None}

    class Config:
        frozen = True


# Functions to instantiate `Settings` instances

_DEFAULTS_CACHE: Settings = None
_FROM_ENV_CACHE: Dict[int, Settings] = {}


def get_current_settings() -> Settings:
    """
    Returns a settings object populated with values from the current settings context
    or, if no settings context is active, the environment.
    """
    from prefect.context import SettingsContext

    settings_context = SettingsContext.get()
    if settings_context is not None:
        return settings_context.settings

    return get_settings_from_env()


def get_settings_from_env() -> Settings:
    """
    Returns a settings object populated with default values and overrides from
    environment variables, ignoring any values in profiles.

    Calls with the same environment return a cached object instead of reconstructing
    to avoid validation overhead.
    """
    # Since os.environ is a Dict[str, str] we can safely hash it by contents, but we
    # must be careful to avoid hashing a generator instead of a tuple
    cache_key = hash(tuple((key, value) for key, value in os.environ.items()))

    if cache_key not in _FROM_ENV_CACHE:
        _FROM_ENV_CACHE[cache_key] = Settings()

    return _FROM_ENV_CACHE[cache_key]


def get_default_settings() -> Settings:
    """
    Returns a settings object populated with default values, ignoring any overrides
    from environment variables or profiles.

    This is cached since the defaults should not change during the lifetime of the
    module.
    """
    global _DEFAULTS_CACHE

    if not _DEFAULTS_CACHE:
        old = os.environ
        try:
            os.environ = {}
            settings = get_settings_from_env()
        finally:
            os.environ = old

        _DEFAULTS_CACHE = settings

    return _DEFAULTS_CACHE


@contextmanager
def temporary_settings(
    updates: Mapping[Setting, Any] = None,
    set_defaults: Mapping[Setting, Any] = None,
    restore_defaults: Iterable[Setting] = None,
) -> Settings:
    """
    Temporarily override the current settings by entering a new profile.

    See `Settings.copy_with_update` for details on different argument behavior.

    Example:
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

    new_settings = context.settings.copy_with_update(
        updates=updates, set_defaults=set_defaults, restore_defaults=restore_defaults
    )

    with prefect.context.SettingsContext(
        profile=context.profile, settings=new_settings
    ):
        yield new_settings


class Profile(pydantic.BaseModel):
    """
    A user profile containing settings.
    """

    name: str
    settings: Dict[Setting, Any] = Field(default_factory=dict)
    source: Optional[Path]

    @pydantic.validator("settings", pre=True)
    def map_names_to_settings(cls, value):
        if value is None:
            return value

        # Cast string setting names to variables
        validated = {}
        for setting, val in value.items():
            if isinstance(setting, str) and setting in SETTING_VARIABLES:
                validated[SETTING_VARIABLES[setting]] = val
            elif isinstance(setting, Setting):
                validated[setting] = val
            else:
                raise ValueError(f"Unknown setting {setting!r}.")

        return validated

    def validate_settings(self) -> None:
        """
        Validate the settings contained in this profile.

        Raises:
            pydantic.ValidationError: When settings do not have valid values.
        """
        # Create a new `Settings` instance with the settings from this profile relying
        # on Pydantic validation to raise an error.
        # We do not return the `Settings` object because this is not the recommended
        # path for constructing settings with a profile. See `use_profile` instead.
        Settings(**{setting.name: value for setting, value in self.settings.items()})

    class Config:
        arbitrary_types_allowed = True


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
        self, name: str, settings: Mapping[Union[Dict, str], Any], source: Path = None
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
                profile.name: {
                    setting.name: value for setting, value in profile.settings.items()
                }
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
        return f"ProfilesCollection(profiles={list(self.profiles_by_name.values())!r}, active={self.active_name!r})>"


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

    profiles = [
        Profile(name=name, settings=settings, source=path)
        for name, settings in raw_profiles.items()
    ]

    return ProfilesCollection(profiles, active=active_profile)


def _write_profiles_to(path: Path, profiles: ProfilesCollection) -> None:
    """
    Write profiles in the given collection to a path as TOML.

    Any existing data not present in the given `profiles` will be deleted.
    """
    return path.write_text(toml.dumps(profiles.to_dict()))


def load_profiles() -> ProfilesCollection:
    """
    Load all profiles from the default and current profile paths.
    """
    profiles = _read_profiles_from(DEFAULT_PROFILES_PATH)

    user_profiles_path = PREFECT_PROFILES_PATH.value()
    if user_profiles_path.exists():
        user_profiles = _read_profiles_from(user_profiles_path)

        # Merge all of the user profiles with the defaults
        for name in user_profiles:
            profiles.update_profile(
                name,
                settings=user_profiles[name].settings,
                source=user_profiles[name].source,
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
    from prefect.context import SettingsContext

    profiles = load_profiles()
    context = SettingsContext.get()

    if context:
        profiles.set_active(context.profile.name)

    return profiles.active_profile


def save_profiles(profiles: ProfilesCollection) -> None:
    """
    Writes all non-default profiles to the current profiles path.
    """
    profiles_path = PREFECT_PROFILES_PATH.value()
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


def update_current_profile(settings: Dict[Union[str, Setting], Any]) -> Profile:
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
        raise MissingProfileError("No profile is currently in use.")

    profiles = load_profiles()

    # Ensure the current profile's settings are present
    profiles.update_profile(current_profile.name, current_profile.settings)
    # Then merge the new settings in
    new_profile = profiles.update_profile(current_profile.name, settings)

    # Validate before saving
    new_profile.validate_settings()

    save_profiles(profiles)

    return profiles[current_profile.name]
