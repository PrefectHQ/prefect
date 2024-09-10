"""
Prefect settings management.

Each setting is defined as a `Setting` type. The name of each setting is stylized in all
caps, matching the environment variable that can be used to change the setting.

All settings defined in this file are used to generate a dynamic Pydantic settings class
called `Settings`. When instantiated, this class will load settings from environment
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
import re
import string
import warnings
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Generic,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from urllib.parse import urlparse

import pydantic
import toml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    create_model,
    field_validator,
    fields,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Literal

from prefect._internal.compatibility.deprecated import generate_deprecation_message
from prefect._internal.schemas.validators import validate_settings
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
        deprecated: bool = False,
        deprecated_start_date: Optional[str] = None,
        deprecated_end_date: Optional[str] = None,
        deprecated_help: str = "",
        deprecated_when_message: str = "",
        deprecated_when: Optional[Callable[[Any], bool]] = None,
        deprecated_renamed_to: Optional["Setting[T]"] = None,
        value_callback: Optional[Callable[["Settings", T], T]] = None,
        is_secret: bool = False,
        **kwargs: Any,
    ) -> None:
        self.field: fields.FieldInfo = Field(**kwargs)
        self.type = type
        self.value_callback = value_callback
        self._name = None
        self.is_secret = is_secret
        self.deprecated = deprecated
        self.deprecated_start_date = deprecated_start_date
        self.deprecated_end_date = deprecated_end_date
        self.deprecated_help = deprecated_help
        self.deprecated_when = deprecated_when or (lambda _: True)
        self.deprecated_when_message = deprecated_when_message
        self.deprecated_renamed_to = deprecated_renamed_to
        self.deprecated_renamed_from = None
        self.__doc__ = self.field.description

        # Validate the deprecation settings, will throw an error at setting definition
        # time if the developer has not configured it correctly
        if deprecated:
            generate_deprecation_message(
                name="...",  # setting names not populated until after init
                start_date=self.deprecated_start_date,
                end_date=self.deprecated_end_date,
                help=self.deprecated_help,
                when=self.deprecated_when_message,
            )

        if deprecated_renamed_to is not None:
            # Track the deprecation both ways
            deprecated_renamed_to.deprecated_renamed_from = self

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
        value = settings.value_of(self, bypass_callback=bypass_callback)

        if not bypass_callback and self.deprecated and self.deprecated_when(value):
            # Check if this setting is deprecated and someone is accessing the value
            # via the old name
            warnings.warn(self.deprecated_message, DeprecationWarning, stacklevel=3)

            # If the the value is empty, return the new setting's value for compat
            if value is None and self.deprecated_renamed_to is not None:
                return self.deprecated_renamed_to.value_from(settings)

        if not bypass_callback and self.deprecated_renamed_from is not None:
            # Check if this setting is a rename of a deprecated setting and the
            # deprecated setting is set and should be used for compatibility
            deprecated_value = self.deprecated_renamed_from.value_from(
                settings, bypass_callback=True
            )
            if deprecated_value is not None:
                warnings.warn(
                    (
                        f"{self.deprecated_renamed_from.deprecated_message} Because"
                        f" {self.deprecated_renamed_from.name!r} is set it will be used"
                        f" instead of {self.name!r} for backwards compatibility."
                    ),
                    DeprecationWarning,
                    stacklevel=3,
                )
            return deprecated_value or value

        return value

    @property
    def name(self):
        if self._name:
            return self._name

        # Lookup the name on first access
        for name, val in tuple(globals().items()):
            if val == self:
                self._name = name
                return name

        raise ValueError("Setting not found in `prefect.settings` module.")

    @name.setter
    def name(self, value: str):
        self._name = value

    @property
    def deprecated_message(self):
        return generate_deprecation_message(
            name=f"Setting {self.name!r}",
            start_date=self.deprecated_start_date,
            end_date=self.deprecated_end_date,
            help=self.deprecated_help,
            when=self.deprecated_when_message,
        )

    def __repr__(self) -> str:
        return f"<{self.name}: {self.type!r}>"

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
    `value_callback` for `PREFECT_UI_API_URL` that sets the default value to
    relative path '/api', otherwise it constructs an API URL from the API settings.
    """
    if value is None:
        # Set a default value
        value = "/api"

    return template_with_settings(
        PREFECT_SERVER_API_HOST, PREFECT_SERVER_API_PORT, PREFECT_API_URL
    )(settings, value)


def status_codes_as_integers_in_range(_, value):
    """
    `value_callback` for `PREFECT_CLIENT_RETRY_EXTRA_CODES` that ensures status codes
    are integers in the range 100-599.
    """
    if value == "":
        return set()

    values = {v.strip() for v in value.split(",")}

    if any(not v.isdigit() or int(v) < 100 or int(v) > 599 for v in values):
        raise ValueError(
            "PREFECT_CLIENT_RETRY_EXTRA_CODES must be a comma separated list of "
            "integers between 100 and 599."
        )

    values = {int(v) for v in values}
    return values


def template_with_settings(*upstream_settings: Setting) -> Callable[["Settings", T], T]:
    """
    Returns a `value_callback` that will template the given settings into the runtime
    value for the setting.
    """

    def templater(settings, value):
        if value is None:
            return value  # Do not attempt to template a null string

        original_type = type(value)
        template_values = {
            setting.name: setting.value_from(settings) for setting in upstream_settings
        }
        template = string.Template(str(value))
        # Note the use of `safe_substitute` to avoid raising an exception if a
        # template value is missing. In this case, template values will be left
        # as-is in the string. Using `safe_substitute` prevents us raising when
        # the DB password contains a `$` character.
        return original_type(template.safe_substitute(template_values))

    return templater


def max_log_size_smaller_than_batch_size(values):
    """
    Validator for settings asserting the batch size and match log size are compatible
    """
    if (
        values["PREFECT_LOGGING_TO_API_BATCH_SIZE"]
        < values["PREFECT_LOGGING_TO_API_MAX_LOG_SIZE"]
    ):
        raise ValueError(
            "`PREFECT_LOGGING_TO_API_MAX_LOG_SIZE` cannot be larger than"
            " `PREFECT_LOGGING_TO_API_BATCH_SIZE`"
        )
    return values


def warn_on_database_password_value_without_usage(values):
    """
    Validator for settings warning if the database password is set but not used.
    """
    value = values["PREFECT_API_DATABASE_PASSWORD"]
    if (
        value
        and not value.startswith(OBFUSCATED_PREFIX)
        and values["PREFECT_API_DATABASE_CONNECTION_URL"] is not None
        and (
            "PREFECT_API_DATABASE_PASSWORD"
            not in values["PREFECT_API_DATABASE_CONNECTION_URL"]
        )
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
    api_url = values["PREFECT_API_URL"]
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


def default_database_connection_url(settings: "Settings", value: Optional[str]):
    driver = PREFECT_API_DATABASE_DRIVER.value_from(settings)
    if driver == "postgresql+asyncpg":
        required = [
            PREFECT_API_DATABASE_HOST,
            PREFECT_API_DATABASE_USER,
            PREFECT_API_DATABASE_NAME,
            PREFECT_API_DATABASE_PASSWORD,
        ]
        missing = [
            setting.name for setting in required if not setting.value_from(settings)
        ]
        if missing:
            raise ValueError(
                f"Missing required database connection settings: {', '.join(missing)}"
            )

        # We only need SQLAlchemy here if we're parsing a remote database connection
        # string.  Import it here so that we don't require the prefect-client package
        # to have SQLAlchemy installed.
        from sqlalchemy import URL

        return URL(
            drivername=driver,
            host=PREFECT_API_DATABASE_HOST.value_from(settings),
            port=PREFECT_API_DATABASE_PORT.value_from(settings) or 5432,
            username=PREFECT_API_DATABASE_USER.value_from(settings),
            password=PREFECT_API_DATABASE_PASSWORD.value_from(settings),
            database=PREFECT_API_DATABASE_NAME.value_from(settings),
            query=[],
        ).render_as_string(hide_password=False)

    elif driver == "sqlite+aiosqlite":
        path = PREFECT_API_DATABASE_NAME.value_from(settings)
        if path:
            return f"{driver}:///{path}"
    elif driver:
        raise ValueError(f"Unsupported database driver: {driver}")

    templater = template_with_settings(PREFECT_HOME, PREFECT_API_DATABASE_PASSWORD)

    # If the user has provided a value, use it
    if value is not None:
        return templater(settings, value)

    # Otherwise, the default is a database in a local file
    home = PREFECT_HOME.value_from(settings)

    old_default = home / "orion.db"
    new_default = home / "prefect.db"

    # If the old one exists and the new one does not, continue using the old one
    if not new_default.exists():
        if old_default.exists():
            return "sqlite+aiosqlite:///" + str(old_default)

    # Otherwise, return the new default
    return "sqlite+aiosqlite:///" + str(new_default)


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

    if re.match(r"^https://api[\.\w]*.prefect.[^\.]+/", api_url):
        ui_url = ui_url.replace("https://api", "https://app", 1)

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

PREFECT_CLI_PROMPT = Setting(
    Optional[bool],
    default=None,
)
"""If `True`, use interactive prompts in CLI commands. If `False`, no interactive
prompts will be used. If `None`, the value will be dynamically determined based on
the presence of an interactive-enabled terminal.
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
behavior to facilitate testing. Defaults to `False`.
"""

PREFECT_UNIT_TEST_MODE = Setting(
    bool,
    default=False,
)
"""
This variable only exists to facilitate unit testing. If `True`,
code is executing in a unit test context. Defaults to `False`.
"""
PREFECT_UNIT_TEST_LOOP_DEBUG = Setting(
    bool,
    default=True,
)
"""
If `True` turns on debug mode for the unit testing event loop.
Defaults to `False`.
"""

PREFECT_TEST_SETTING = Setting(
    Any,
    default=None,
    value_callback=only_return_value_in_test_mode,
)
"""
This variable only exists to facilitate testing of settings.
If accessed when `PREFECT_TEST_MODE` is not set, `None` is returned.
"""

PREFECT_API_TLS_INSECURE_SKIP_VERIFY = Setting(
    bool,
    default=False,
)
"""If `True`, disables SSL checking to allow insecure requests.
This is recommended only during development, e.g. when using self-signed certificates.
"""

PREFECT_API_SSL_CERT_FILE = Setting(
    Optional[str],
    default=os.environ.get("SSL_CERT_FILE"),
)
"""
This configuration settings option specifies the path to an SSL certificate file.
When set, it allows the application to use the specified certificate for secure communication.
If left unset, the setting will default to the value provided by the `SSL_CERT_FILE` environment variable.
"""

PREFECT_API_URL = Setting(
    Optional[str],
    default=None,
)
"""
If provided, the URL of a hosted Prefect API. Defaults to `None`.

When using Prefect Cloud, this will include an account and workspace.
"""

PREFECT_SILENCE_API_URL_MISCONFIGURATION = Setting(
    bool,
    default=False,
)
"""If `True`, disable the warning when a user accidentally misconfigure its `PREFECT_API_URL`
Sometimes when a user manually set `PREFECT_API_URL` to a custom url,reverse-proxy for example,
we would like to silence this warning so we will set it to `FALSE`.
"""

PREFECT_API_KEY = Setting(
    Optional[str],
    default=None,
    is_secret=True,
)
"""API key used to authenticate with a the Prefect API. Defaults to `None`."""

PREFECT_API_ENABLE_HTTP2 = Setting(bool, default=False)
"""
If true, enable support for HTTP/2 for communicating with an API.

If the API does not support HTTP/2, this will have no effect and connections will be
made via HTTP/1.1.
"""


PREFECT_CLIENT_MAX_RETRIES = Setting(int, default=5)
"""
The maximum number of retries to perform on failed HTTP requests.

Defaults to 5.
Set to 0 to disable retries.

See `PREFECT_CLIENT_RETRY_EXTRA_CODES` for details on which HTTP status codes are
retried.
"""

PREFECT_CLIENT_RETRY_JITTER_FACTOR = Setting(float, default=0.2)
"""
A value greater than or equal to zero to control the amount of jitter added to retried
client requests. Higher values introduce larger amounts of jitter.

Set to 0 to disable jitter. See `clamped_poisson_interval` for details on the how jitter
can affect retry lengths.
"""


PREFECT_CLIENT_RETRY_EXTRA_CODES = Setting(
    str, default="", value_callback=status_codes_as_integers_in_range
)
"""
A comma-separated list of extra HTTP status codes to retry on. Defaults to an empty string.
429, 502 and 503 are always retried. Please note that not all routes are idempotent and retrying
may result in unexpected behavior.
"""

PREFECT_CLIENT_CSRF_SUPPORT_ENABLED = Setting(bool, default=True)
"""
Determines if CSRF token handling is active in the Prefect client for API
requests.

When enabled (`True`), the client automatically manages CSRF tokens by
retrieving, storing, and including them in applicable state-changing requests
(POST, PUT, PATCH, DELETE) to the API.

Disabling this setting (`False`) means the client will not handle CSRF tokens,
which might be suitable for environments where CSRF protection is disabled.

Defaults to `True`, ensuring CSRF protection is enabled by default.
"""

PREFECT_CLOUD_API_URL = Setting(
    str,
    default="https://api.prefect.cloud/api",
)
"""API URL for Prefect Cloud. Used for authentication."""


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
    Optional[str],
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
    default=60.0,
)
"""The default timeout for requests to the API"""

PREFECT_EXPERIMENTAL_WARN = Setting(bool, default=True)
"""
If enabled, warn on usage of experimental features.
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

PREFECT_TASKS_REFRESH_CACHE = Setting(
    bool,
    default=False,
)
"""
If `True`, enables a refresh of cached results: re-executing the
task will refresh the cached results. Defaults to `False`.
"""

PREFECT_TASK_DEFAULT_RETRIES = Setting(int, default=0)
"""
This value sets the default number of retries for all tasks.
This value does not overwrite individually set retries values on tasks
"""

PREFECT_FLOW_DEFAULT_RETRIES = Setting(int, default=0)
"""
This value sets the default number of retries for all flows.
This value does not overwrite individually set retries values on a flow
"""

PREFECT_FLOW_DEFAULT_RETRY_DELAY_SECONDS = Setting(Union[int, float], default=0)
"""
This value sets the retry delay seconds for all flows.
This value does not overwrite individually set retry delay seconds
"""

PREFECT_TASK_DEFAULT_RETRY_DELAY_SECONDS = Setting(
    Union[float, int, List[float]], default=0
)
"""
This value sets the default retry delay seconds for all tasks.
This value does not overwrite individually set retry delay seconds
"""

PREFECT_TASK_RUN_TAG_CONCURRENCY_SLOT_WAIT_SECONDS = Setting(int, default=30)
"""
The number of seconds to wait before retrying when a task run
cannot secure a concurrency slot from the server.
"""

PREFECT_LOCAL_STORAGE_PATH = Setting(
    Path,
    default=Path("${PREFECT_HOME}") / "storage",
    value_callback=template_with_settings(PREFECT_HOME),
)
"""The path to a block storage directory to store things in."""

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


PREFECT_LOGGING_INTERNAL_LEVEL = Setting(
    str,
    default="ERROR",
    value_callback=debug_mode_log_level,
)
"""
The default logging level for Prefect's internal machinery loggers. Defaults to
"ERROR" during normal operation. Is forced to "DEBUG" during debug mode.
"""

PREFECT_LOGGING_SERVER_LEVEL = Setting(
    str,
    default="WARNING",
)
"""The default logging level for the Prefect API server."""

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
for the given run. This setting can be overridden by individual tasks and flows.
"""

PREFECT_LOGGING_TO_API_ENABLED = Setting(
    bool,
    default=True,
)
"""
Toggles sending logs to the API.
If `False`, logs sent to the API log handler will not be sent to the API.
"""

PREFECT_LOGGING_TO_API_BATCH_INTERVAL = Setting(float, default=2.0)
"""The number of seconds between batched writes of logs to the API."""

PREFECT_LOGGING_TO_API_BATCH_SIZE = Setting(
    int,
    default=4_000_000,
)
"""The maximum size in bytes for a batch of logs."""

PREFECT_LOGGING_TO_API_MAX_LOG_SIZE = Setting(
    int,
    default=1_000_000,
)
"""The maximum size in bytes for a single log."""

PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW = Setting(
    Literal["warn", "error", "ignore"],
    default="warn",
)
"""
Controls the behavior when loggers attempt to send logs to the API handler from outside
of a flow.

All logs sent to the API must be associated with a flow run. The API log handler can
only be used outside of a flow by manually providing a flow run identifier. Logs
that are not associated with a flow run will not be sent to the API. This setting can
be used to determine if a warning or error is displayed when the identifier is missing.

The following options are available:

- "warn": Log a warning message.
- "error": Raise an error.
- "ignore": Do not log a warning message or raise an error.
"""

PREFECT_SQLALCHEMY_POOL_SIZE = Setting(
    Optional[int],
    default=None,
)
"""
Controls connection pool size when using a PostgreSQL database with the Prefect API. If not set, the default SQLAlchemy pool size will be used.
"""

PREFECT_SQLALCHEMY_MAX_OVERFLOW = Setting(
    Optional[int],
    default=None,
)
"""
Controls maximum overflow of the connection pool when using a PostgreSQL database with the Prefect API. If not set, the default SQLAlchemy maximum overflow value will be used.
"""

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

PREFECT_ASYNC_FETCH_STATE_RESULT = Setting(bool, default=False)
"""
Determines whether `State.result()` fetches results automatically or not.
In Prefect 2.6.0, the `State.result()` method was updated to be async
to facilitate automatic retrieval of results from storage which means when
writing async code you must `await` the call. For backwards compatibility,
the result is not retrieved by default for async users. You may opt into this
per call by passing  `fetch=True` or toggle this setting to change the behavior
globally.
This setting does not affect users writing synchronous tasks and flows.
This setting does not affect retrieval of results when using `Future.result()`.
"""


PREFECT_API_BLOCKS_REGISTER_ON_START = Setting(
    bool,
    default=True,
)
"""
If set, any block types that have been imported will be registered with the
backend on application startup. If not set, block types must be manually
registered.
"""

PREFECT_API_DATABASE_CONNECTION_URL = Setting(
    Optional[str],
    default=None,
    value_callback=default_database_connection_url,
    is_secret=True,
)
"""
A database connection URL in a SQLAlchemy-compatible
format. Prefect currently supports SQLite and Postgres. Note that all
Prefect database engines must use an async driver - for SQLite, use
`sqlite+aiosqlite` and for Postgres use `postgresql+asyncpg`.

SQLite in-memory databases can be used by providing the url
`sqlite+aiosqlite:///file::memory:?cache=shared&uri=true&check_same_thread=false`,
which will allow the database to be accessed by multiple threads. Note
that in-memory databases can not be accessed from multiple processes and
should only be used for simple tests.

Defaults to a sqlite database stored in the Prefect home directory.

If you need to provide password via a different environment variable, you use
the `PREFECT_API_DATABASE_PASSWORD` setting. For example:

```
PREFECT_API_DATABASE_PASSWORD='mypassword'
PREFECT_API_DATABASE_CONNECTION_URL='postgresql+asyncpg://postgres:${PREFECT_API_DATABASE_PASSWORD}@localhost/prefect'
```
"""

PREFECT_API_DATABASE_DRIVER = Setting(
    Optional[Literal["postgresql+asyncpg", "sqlite+aiosqlite"]],
    default=None,
)
"""
The database driver to use when connecting to the database.
"""

PREFECT_API_DATABASE_HOST = Setting(Optional[str], default=None)
"""
The database server host.
"""

PREFECT_API_DATABASE_PORT = Setting(Optional[int], default=None)
"""
The database server port.
"""

PREFECT_API_DATABASE_USER = Setting(Optional[str], default=None)
"""
The user to use when connecting to the database.
"""

PREFECT_API_DATABASE_NAME = Setting(Optional[str], default=None)
"""
The name of the Prefect database on the remote server, or the path to the database file
for SQLite.
"""

PREFECT_API_DATABASE_PASSWORD = Setting(
    Optional[str],
    default=None,
    is_secret=True,
)
"""
Password to template into the `PREFECT_API_DATABASE_CONNECTION_URL`.
This is useful if the password must be provided separately from the connection URL.
To use this setting, you must include it in your connection URL.
"""

PREFECT_API_DATABASE_ECHO = Setting(
    bool,
    default=False,
)
"""If `True`, SQLAlchemy will log all SQL issued to the database. Defaults to `False`."""

PREFECT_API_DATABASE_MIGRATE_ON_START = Setting(
    bool,
    default=True,
)
"""If `True`, the database will be upgraded on application creation. If `False`, the database will need to be upgraded manually."""

PREFECT_API_DATABASE_TIMEOUT = Setting(
    Optional[float],
    default=10.0,
)
"""
A statement timeout, in seconds, applied to all database interactions made by the API.
Defaults to 10 seconds.
"""

PREFECT_API_DATABASE_CONNECTION_TIMEOUT = Setting(
    Optional[float],
    default=5,
)
"""A connection timeout, in seconds, applied to database
connections. Defaults to `5`.
"""

PREFECT_API_SERVICES_SCHEDULER_LOOP_SECONDS = Setting(
    float,
    default=60,
)
"""The scheduler loop interval, in seconds. This determines
how often the scheduler will attempt to schedule new flow runs, but has no
impact on how quickly either flow runs or task runs are actually executed.
Defaults to `60`.
"""

PREFECT_API_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE = Setting(
    int,
    default=100,
)
"""The number of deployments the scheduler will attempt to
schedule in a single batch. If there are more deployments than the batch
size, the scheduler immediately attempts to schedule the next batch; it
does not sleep for `scheduler_loop_seconds` until it has visited every
deployment once. Defaults to `100`.
"""

PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS = Setting(
    int,
    default=100,
)
"""The scheduler will attempt to schedule up to this many
auto-scheduled runs in the future. Note that runs may have fewer than
this many scheduled runs, depending on the value of
`scheduler_max_scheduled_time`.  Defaults to `100`.
"""

PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS = Setting(
    int,
    default=3,
)
"""The scheduler will attempt to schedule at least this many
auto-scheduled runs in the future. Note that runs may have more than
this many scheduled runs, depending on the value of
`scheduler_min_scheduled_time`.  Defaults to `3`.
"""

PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME = Setting(
    timedelta,
    default=timedelta(days=100),
)
"""The scheduler will create new runs up to this far in the
future. Note that this setting will take precedence over
`scheduler_max_runs`: if a flow runs once a month and
`scheduler_max_scheduled_time` is three months, then only three runs will be
scheduled. Defaults to 100 days (`8640000` seconds).
"""

PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME = Setting(
    timedelta,
    default=timedelta(hours=1),
)
"""The scheduler will create new runs at least this far in the
future. Note that this setting will take precedence over `scheduler_min_runs`:
if a flow runs every hour and `scheduler_min_scheduled_time` is three hours,
then three runs will be scheduled even if `scheduler_min_runs` is 1. Defaults to
1 hour (`3600` seconds).
"""

PREFECT_API_SERVICES_SCHEDULER_INSERT_BATCH_SIZE = Setting(
    int,
    default=500,
)
"""The number of flow runs the scheduler will attempt to insert
in one batch across all deployments. If the number of flow runs to
schedule exceeds this amount, the runs will be inserted in batches of this size.
Defaults to `500`.
"""

PREFECT_API_SERVICES_LATE_RUNS_LOOP_SECONDS = Setting(
    float,
    default=5,
)
"""The late runs service will look for runs to mark as late
this often. Defaults to `5`.
"""

PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS = Setting(
    timedelta,
    default=timedelta(seconds=15),
)
"""The late runs service will mark runs as late after they
have exceeded their scheduled start time by this many seconds. Defaults
to `5` seconds.
"""

PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_LOOP_SECONDS = Setting(
    float,
    default=5,
)
"""The pause expiration service will look for runs to mark as failed
this often. Defaults to `5`.
"""

PREFECT_API_SERVICES_CANCELLATION_CLEANUP_LOOP_SECONDS = Setting(
    float,
    default=20,
)
"""The cancellation cleanup service will look non-terminal tasks and subflows
this often. Defaults to `20`.
"""

PREFECT_API_SERVICES_FOREMAN_ENABLED = Setting(bool, default=True)
"""Whether or not to start the Foreman service in the server application."""

PREFECT_API_SERVICES_FOREMAN_LOOP_SECONDS = Setting(float, default=15)
"""The number of seconds to wait between each iteration of the Foreman loop which checks
for offline workers and updates work pool status."""


PREFECT_API_SERVICES_FOREMAN_INACTIVITY_HEARTBEAT_MULTIPLE = Setting(int, default=3)
"The number of heartbeats that must be missed before a worker is marked as offline."

PREFECT_API_SERVICES_FOREMAN_FALLBACK_HEARTBEAT_INTERVAL_SECONDS = Setting(
    int, default=30
)
"""The number of seconds to use for online/offline evaluation if a worker's heartbeat
interval is not set."""

PREFECT_API_SERVICES_FOREMAN_DEPLOYMENT_LAST_POLLED_TIMEOUT_SECONDS = Setting(
    int, default=60
)
"""The number of seconds before a deployment is marked as not ready if it has not been
polled."""

PREFECT_API_SERVICES_FOREMAN_WORK_QUEUE_LAST_POLLED_TIMEOUT_SECONDS = Setting(
    int, default=60
)
"""The number of seconds before a work queue is marked as not ready if it has not been
polled."""

PREFECT_API_LOG_RETRYABLE_ERRORS = Setting(bool, default=False)
"""If `True`, log retryable errors in the API and it's services."""

PREFECT_API_SERVICES_TASK_RUN_RECORDER_ENABLED = Setting(bool, default=True)
"""
Whether or not to start the task run recorder service in the server application.
"""


PREFECT_API_DEFAULT_LIMIT = Setting(
    int,
    default=200,
)
"""The default limit applied to queries that can return
multiple objects, such as `POST /flow_runs/filter`.
"""

PREFECT_SERVER_API_HOST = Setting(
    str,
    default="127.0.0.1",
)
"""The API's host address (defaults to `127.0.0.1`)."""

PREFECT_SERVER_API_PORT = Setting(
    int,
    default=4200,
)
"""The API's port address (defaults to `4200`)."""

PREFECT_SERVER_API_KEEPALIVE_TIMEOUT = Setting(
    int,
    default=5,
)
"""
The API's keep alive timeout (defaults to `5`).
Refer to https://www.uvicorn.org/settings/#timeouts for details.

When the API is hosted behind a load balancer, you may want to set this to a value
greater than the load balancer's idle timeout.

Note this setting only applies when calling `prefect server start`; if hosting the
API with another tool you will need to configure this there instead.
"""

PREFECT_SERVER_CSRF_PROTECTION_ENABLED = Setting(bool, default=False)
"""
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
"""

PREFECT_SERVER_CSRF_TOKEN_EXPIRATION = Setting(timedelta, default=timedelta(hours=1))
"""
Specifies the duration for which a CSRF token remains valid after being issued
by the server.

The default expiration time is set to 1 hour, which offers a reasonable
compromise. Adjust this setting based on your specific security requirements
and usage patterns.
"""

PREFECT_SERVER_ALLOW_EPHEMERAL_MODE = Setting(bool, default=False)
"""
Controls whether or not a subprocess server can be started when no API URL is provided.
"""

PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS = Setting(
    int,
    default=10,
)
"""
The number of seconds to wait for an ephemeral server to respond on start up before erroring.
"""

PREFECT_UI_ENABLED = Setting(
    bool,
    default=True,
)
"""Whether or not to serve the Prefect UI."""

PREFECT_UI_API_URL = Setting(
    Optional[str],
    default=None,
    value_callback=default_ui_api_url,
)
"""The connection url for communication from the UI to the API.
Defaults to `PREFECT_API_URL` if set. Otherwise, the default URL is generated from
`PREFECT_SERVER_API_HOST` and `PREFECT_SERVER_API_PORT`. If providing a custom value,
the aforementioned settings may be templated into the given string.
"""

PREFECT_SERVER_ANALYTICS_ENABLED = Setting(
    bool,
    default=True,
)
"""
When enabled, Prefect sends anonymous data (e.g. count of flow runs, package version)
on server startup to help us improve our product.
"""

PREFECT_API_SERVICES_SCHEDULER_ENABLED = Setting(
    bool,
    default=True,
)
"""Whether or not to start the scheduling service in the server application.
If disabled, you will need to run this service separately to schedule runs for deployments.
"""

PREFECT_API_SERVICES_LATE_RUNS_ENABLED = Setting(
    bool,
    default=True,
)
"""Whether or not to start the late runs service in the server application.
If disabled, you will need to run this service separately to have runs past their
scheduled start time marked as late.
"""

PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED = Setting(
    bool,
    default=True,
)
"""Whether or not to start the flow run notifications service in the server application.
If disabled, you will need to run this service separately to send flow run notifications.
"""

PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_ENABLED = Setting(
    bool,
    default=True,
)
"""Whether or not to start the paused flow run expiration service in the server
application. If disabled, paused flows that have timed out will remain in a Paused state
until a resume attempt.
"""

PREFECT_API_TASK_CACHE_KEY_MAX_LENGTH = Setting(int, default=2000)
"""
The maximum number of characters allowed for a task run cache key.
This setting cannot be changed client-side, it must be set on the server.
"""

PREFECT_API_SERVICES_CANCELLATION_CLEANUP_ENABLED = Setting(
    bool,
    default=True,
)
"""Whether or not to start the cancellation cleanup service in the server
application. If disabled, task runs and subflow runs belonging to cancelled flows may
remain in non-terminal states.
"""

PREFECT_API_MAX_FLOW_RUN_GRAPH_NODES = Setting(int, default=10000)
"""
The maximum size of a flow run graph on the v2 API
"""

PREFECT_API_MAX_FLOW_RUN_GRAPH_ARTIFACTS = Setting(int, default=10000)
"""
The maximum number of artifacts to show on a flow run graph on the v2 API
"""

# Prefect Events feature flags

PREFECT_RUNNER_PROCESS_LIMIT = Setting(int, default=5)
"""
Maximum number of processes a runner will execute in parallel.
"""

PREFECT_RUNNER_POLL_FREQUENCY = Setting(int, default=10)
"""
Number of seconds a runner should wait between queries for scheduled work.
"""

PREFECT_RUNNER_SERVER_MISSED_POLLS_TOLERANCE = Setting(int, default=2)
"""
Number of missed polls before a runner is considered unhealthy by its webserver.
"""

PREFECT_RUNNER_SERVER_HOST = Setting(str, default="localhost")
"""
The host address the runner's webserver should bind to.
"""

PREFECT_RUNNER_SERVER_PORT = Setting(int, default=8080)
"""
The port the runner's webserver should bind to.
"""

PREFECT_RUNNER_SERVER_LOG_LEVEL = Setting(str, default="error")
"""
The log level of the runner's webserver.
"""

PREFECT_RUNNER_SERVER_ENABLE = Setting(bool, default=False)
"""
Whether or not to enable the runner's webserver.
"""

PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS = Setting(int, default=50)
"""
The maximum number of scheduled runs to create for a deployment.
"""

PREFECT_WORKER_HEARTBEAT_SECONDS = Setting(float, default=30)
"""
Number of seconds a worker should wait between sending a heartbeat.
"""

PREFECT_WORKER_QUERY_SECONDS = Setting(float, default=10)
"""
Number of seconds a worker should wait between queries for scheduled flow runs.
"""

PREFECT_WORKER_PREFETCH_SECONDS = Setting(float, default=10)
"""
The number of seconds into the future a worker should query for scheduled flow runs.
Can be used to compensate for infrastructure start up time for a worker.
"""

PREFECT_WORKER_WEBSERVER_HOST = Setting(
    str,
    default="0.0.0.0",
)
"""
The host address the worker's webserver should bind to.
"""

PREFECT_WORKER_WEBSERVER_PORT = Setting(
    int,
    default=8080,
)
"""
The port the worker's webserver should bind to.
"""

PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK = Setting(Optional[str], default=None)
"""The `block-type/block-document` slug of a block to use as the default storage
for autonomous tasks."""

PREFECT_TASK_SCHEDULING_DELETE_FAILED_SUBMISSIONS = Setting(
    bool,
    default=True,
)
"""
Whether or not to delete failed task submissions from the database.
"""

PREFECT_TASK_SCHEDULING_MAX_SCHEDULED_QUEUE_SIZE = Setting(
    int,
    default=1000,
)
"""
The maximum number of scheduled tasks to queue for submission.
"""

PREFECT_TASK_SCHEDULING_MAX_RETRY_QUEUE_SIZE = Setting(
    int,
    default=100,
)
"""
The maximum number of retries to queue for submission.
"""

PREFECT_TASK_SCHEDULING_PENDING_TASK_TIMEOUT = Setting(
    timedelta,
    default=timedelta(0),
)
"""
How long before a PENDING task are made available to another task worker.  In practice,
a task worker should move a task from PENDING to RUNNING very quickly, so runs stuck in
PENDING for a while is a sign that the task worker may have crashed.
"""

PREFECT_EXPERIMENTAL_ENABLE_SCHEDULE_CONCURRENCY = Setting(bool, default=False)

# Defaults -----------------------------------------------------------------------------

PREFECT_DEFAULT_RESULT_STORAGE_BLOCK = Setting(
    Optional[str],
    default=None,
)
"""The `block-type/block-document` slug of a block to use as the default result storage."""

PREFECT_DEFAULT_WORK_POOL_NAME = Setting(Optional[str], default=None)
"""
The default work pool to deploy to.
"""

PREFECT_DEFAULT_DOCKER_BUILD_NAMESPACE = Setting(
    Optional[str],
    default=None,
)
"""
The default Docker namespace to use when building images.

Can be either an organization/username or a registry URL with an organization/username.
"""

PREFECT_UI_SERVE_BASE = Setting(
    str,
    default="/",
)
"""
The base URL path to serve the Prefect UI from.

Defaults to the root path.
"""

PREFECT_UI_STATIC_DIRECTORY = Setting(
    Optional[str],
    default=None,
)
"""
The directory to serve static files from. This should be used when running into permissions issues
when attempting to serve the UI from the default directory (for example when running in a Docker container)
"""

# Messaging system settings

PREFECT_MESSAGING_BROKER = Setting(
    str, default="prefect.server.utilities.messaging.memory"
)
"""
Which message broker implementation to use for the messaging system, should point to a
module that exports a Publisher and Consumer class.
"""

PREFECT_MESSAGING_CACHE = Setting(
    str, default="prefect.server.utilities.messaging.memory"
)
"""
Which cache implementation to use for the events system.  Should point to a module that
exports a Cache class.
"""


# Events settings

PREFECT_EVENTS_MAXIMUM_LABELS_PER_RESOURCE = Setting(int, default=500)
"""
The maximum number of labels a resource may have.
"""

PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES = Setting(int, default=500)
"""
The maximum number of related resources an Event may have.
"""

PREFECT_EVENTS_MAXIMUM_SIZE_BYTES = Setting(int, default=1_500_000)
"""
The maximum size of an Event when serialized to JSON
"""

PREFECT_API_SERVICES_TRIGGERS_ENABLED = Setting(bool, default=True)
"""
Whether or not to start the triggers service in the server application.
"""

PREFECT_EVENTS_EXPIRED_BUCKET_BUFFER = Setting(timedelta, default=timedelta(seconds=60))
"""
The amount of time to retain expired automation buckets
"""

PREFECT_EVENTS_PROACTIVE_GRANULARITY = Setting(timedelta, default=timedelta(seconds=5))
"""
How frequently proactive automations are evaluated
"""

PREFECT_API_SERVICES_EVENT_PERSISTER_ENABLED = Setting(bool, default=True)
"""
Whether or not to start the event persister service in the server application.
"""

PREFECT_API_SERVICES_EVENT_PERSISTER_BATCH_SIZE = Setting(int, default=20, gt=0)
"""
The number of events the event persister will attempt to insert in one batch.
"""

PREFECT_API_SERVICES_EVENT_PERSISTER_FLUSH_INTERVAL = Setting(float, default=5, gt=0.0)
"""
The maximum number of seconds between flushes of the event persister.
"""

PREFECT_EVENTS_RETENTION_PERIOD = Setting(timedelta, default=timedelta(days=7))
"""
The amount of time to retain events in the database.
"""

PREFECT_API_EVENTS_STREAM_OUT_ENABLED = Setting(bool, default=True)
"""
Whether or not to allow streaming events out of via websockets.
"""

PREFECT_API_EVENTS_RELATED_RESOURCE_CACHE_TTL = Setting(
    timedelta, default=timedelta(minutes=5)
)
"""
How long to cache related resource data for emitting server-side vents
"""

PREFECT_EVENTS_MAXIMUM_WEBSOCKET_BACKFILL = Setting(
    timedelta, default=timedelta(minutes=15)
)
"""
The maximum range to look back for backfilling events for a websocket subscriber
"""

PREFECT_EVENTS_WEBSOCKET_BACKFILL_PAGE_SIZE = Setting(int, default=250, gt=0)
"""
The page size for the queries to backfill events for websocket subscribers
"""


# Metrics settings

PREFECT_API_ENABLE_METRICS = Setting(bool, default=False)
"""
Whether or not to enable Prometheus metrics in the server application.  Metrics are
served at the path /api/metrics on the API server.
"""

PREFECT_CLIENT_ENABLE_METRICS = Setting(bool, default=False)
"""
Whether or not to enable Prometheus metrics in the client SDK.  Metrics are served
at the path /metrics.
"""

PREFECT_CLIENT_METRICS_PORT = Setting(int, default=4201)
"""
The port to expose the client Prometheus metrics on.
"""


# Deprecated settings ------------------------------------------------------------------


# Collect all defined settings ---------------------------------------------------------

SETTING_VARIABLES: Dict[str, Any] = {
    name: val for name, val in tuple(globals().items()) if isinstance(val, Setting)
}

# Populate names in settings objects from assignments above
# Uses `__` to avoid setting these as global variables which can lead to sneaky bugs

for __name, __setting in SETTING_VARIABLES.items():
    __setting._name = __name

# Dynamically create a pydantic model that includes all of our settings


class PrefectBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")


SettingsFieldsMixin: Type[BaseSettings] = create_model(
    "SettingsFieldsMixin",
    __base__=PrefectBaseSettings,  # Inheriting from `BaseSettings` provides environment variable loading
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

    @field_validator(PREFECT_LOGGING_LEVEL.name, PREFECT_LOGGING_SERVER_LEVEL.name)
    def check_valid_log_level(cls, value):
        if isinstance(value, str):
            value = value.upper()
        logging._checkLevel(value)
        return value

    @model_validator(mode="after")
    def emit_warnings(self):
        """
        Add root validation functions for settings here.
        """
        # TODO: We could probably register these dynamically but this is the simpler
        #       approach for now. We can explore more interesting validation features
        #       in the future.
        values = self.model_dump()
        values = max_log_size_smaller_than_batch_size(values)
        values = warn_on_database_password_value_without_usage(values)
        if not values["PREFECT_SILENCE_API_URL_MISCONFIGURATION"]:
            values = warn_on_misconfigured_api_url(values)
        return self

    def copy_with_update(
        self,
        updates: Optional[Mapping[Setting, Any]] = None,
        set_defaults: Optional[Mapping[Setting, Any]] = None,
        restore_defaults: Optional[Iterable[Setting]] = None,
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
                **self.model_dump(exclude_unset=True, exclude=restore_defaults_names),
                **{setting.name: value for setting, value in updates.items()},
            }
        )

    def with_obfuscated_secrets(self):
        """
        Returns a copy of this settings object with secret setting values obfuscated.
        """
        settings = self.model_copy(
            update={
                setting.name: obfuscate(self.value_of(setting))
                for setting in SETTING_VARIABLES.values()
                if setting.is_secret
                # Exclude deprecated settings with null values to avoid warnings
                and not (setting.deprecated and self.value_of(setting) is None)
            }
        )
        # Ensure that settings that have not been marked as "set" before are still so
        # after we have updated their value above
        with warnings.catch_warnings():
            warnings.simplefilter(
                "ignore", category=pydantic.warnings.PydanticDeprecatedSince20
            )
            settings.__fields_set__.intersection_update(self.__fields_set__)
        return settings

    def hash_key(self) -> str:
        """
        Return a hash key for the settings object.  This is needed since some
        settings may be unhashable.  An example is lists.
        """
        env_variables = self.to_environment_variables()
        return str(hash(tuple((key, value) for key, value in env_variables.items())))

    def to_environment_variables(
        self, include: Optional[Iterable[Setting]] = None, exclude_unset: bool = False
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
                for key in self.model_dump(exclude_unset=True)
            }
            include.intersection_update(set_keys)

        # Validate the types of items in `include` to prevent exclusion bugs
        for key in include:
            if not isinstance(key, Setting):
                raise TypeError(
                    "Invalid type {type(key).__name__!r} for key in `include`."
                )

        env: dict[str, Any] = self.model_dump(
            mode="json", include={s.name for s in include}
        )

        # Cast to strings and drop null values
        return {key: str(value) for key, value in env.items() if value is not None}

    model_config = ConfigDict(frozen=True)


# Functions to instantiate `Settings` instances

_DEFAULTS_CACHE: Optional[Settings] = None
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
    updates: Optional[Mapping[Setting[T], Any]] = None,
    set_defaults: Optional[Mapping[Setting[T], Any]] = None,
    restore_defaults: Optional[Iterable[Setting[T]]] = None,
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

    new_settings = context.settings.copy_with_update(
        updates=updates, set_defaults=set_defaults, restore_defaults=restore_defaults
    )

    with prefect.context.SettingsContext(
        profile=context.profile, settings=new_settings
    ):
        yield new_settings


class Profile(BaseModel):
    """
    A user profile containing settings.
    """

    name: str
    settings: Dict[Setting, Any] = Field(default_factory=dict)
    source: Optional[Path] = None
    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    @field_validator("settings", mode="before")
    def map_names_to_settings(cls, value):
        return validate_settings(value)

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

    def convert_deprecated_renamed_settings(self) -> List[Tuple[Setting, Setting]]:
        """
        Update settings in place to replace deprecated settings with new settings when
        renamed.

        Returns a list of tuples with the old and new setting.
        """
        changed = []
        for setting in tuple(self.settings):
            if (
                setting.deprecated
                and setting.deprecated_renamed_to
                and setting.deprecated_renamed_to not in self.settings
            ):
                self.settings[setting.deprecated_renamed_to] = self.settings.pop(
                    setting
                )
                changed.append((setting, setting.deprecated_renamed_to))
        return changed


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
        path.touch(mode=0o600)
    return path.write_text(toml.dumps(profiles.to_dict()))


def load_profiles(include_defaults: bool = True) -> ProfilesCollection:
    """
    Load profiles from the current profile path. Optionally include profiles from the
    default profile path.
    """
    default_profiles = _read_profiles_from(DEFAULT_PROFILES_PATH)

    if not include_defaults:
        if not PREFECT_PROFILES_PATH.value().exists():
            return ProfilesCollection([])
        return _read_profiles_from(PREFECT_PROFILES_PATH.value())

    user_profiles_path = PREFECT_PROFILES_PATH.value()
    profiles = default_profiles
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
