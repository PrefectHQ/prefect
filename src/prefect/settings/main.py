import os
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import AfterValidator, Field
from pydantic_settings import BaseSettings


class PrefectSettings(BaseSettings):
    PREFECT_API_BLOCKS_REGISTER_ON_START: bool = Field(
        default=True,
        description="""If set, any block types that have been imported will be registered with the backend on application startup. If not set, block types must be manually registered.""",
    )

    PREFECT_API_DATABASE_CONNECTION_TIMEOUT: Optional[float] = Field(
        default=5,
        description="""A connection timeout, in seconds, applied to database connections. Defaults to `5`.""",
    )

    PREFECT_API_DATABASE_CONNECTION_URL: Optional[str] = Field(
        default=None,
        description="""A database connection URL in a SQLAlchemy-compatible format. Prefect currently supports SQLite and Postgres. Note that all Prefect database engines must use an async driver - for SQLite, use `sqlite+aiosqlite` and for Postgres use `postgresql+asyncpg`. SQLite in-memory databases can be used by providing the url `sqlite+aiosqlite:///file::memory:?cache=shared&uri=true&check_same_thread=false`, which will allow the database to be accessed by multiple threads. Note that in-memory databases can not be accessed from multiple processes and should only be used for simple tests. Defaults to a sqlite database stored in the Prefect home directory. If you need to provide password via a different environment variable, you use the `    PREFECT_API_DATABASE_PASSWORD` setting. For example: ```     PREFECT_API_DATABASE_PASSWORD='mypassword'     PREFECT_API_DATABASE_CONNECTION_URL='postgresql+asyncpg://postgres:${PREFECT_API_DATABASE_PASSWORD}@localhost/prefect' ```""",
    )

    PREFECT_API_DATABASE_ECHO: bool = Field(
        default=False,
        description="""If `True`, SQLAlchemy will log all SQL issued to the database. Defaults to `False`.""",
    )

    PREFECT_API_DATABASE_MIGRATE_ON_START: bool = Field(
        default=True,
        description="""If `True`, the database will be upgraded on application creation. If `False`, the database will need to be upgraded manually.""",
    )

    PREFECT_API_DATABASE_PASSWORD: Optional[str] = Field(
        default=None,
        description="""Password to template into the `    PREFECT_API_DATABASE_CONNECTION_URL`. This is useful if the password must be provided separately from the connection URL. To use this setting, you must include it in your connection URL.""",
    )

    PREFECT_API_DATABASE_TIMEOUT: Optional[float] = Field(
        default=10.0,
        description="""A statement timeout, in seconds, applied to all database interactions made by the API. Defaults to 10 seconds.""",
    )

    PREFECT_API_DEFAULT_LIMIT: int = Field(
        default=200, description="""The API's host address (defaults to `127.0.0.1`)."""
    )

    PREFECT_API_EVENTS_RELATED_RESOURCE_CACHE_TTL: timedelta = Field(
        default=timedelta(minutes=5), description="""Retrieve a setting's value."""
    )

    PREFECT_API_EVENTS_STREAM_OUT_ENABLED: bool = Field(
        default=True,
        description="""Contains validated Prefect settings. Settings should be accessed using the relevant `Setting` object. For example: ```python from prefect.settings import     PREFECT_HOME     PREFECT_HOME.value() ``` Accessing a setting attribute directly will ignore any `value_callback` mutations. This is not recommended: ```python from prefect.settings import Settings Settings().    PREFECT_PROFILES_PATH # PosixPath('${PREFECT_HOME}/profiles.toml') ```""",
    )

    PREFECT_API_KEY: Optional[str] = Field(
        default=None,
        description="""API key used to authenticate with a the Prefect API. Defaults to `None`.""",
    )

    PREFECT_API_LOG_RETRYABLE_ERRORS: bool = Field(
        default=False,
        description="""The default limit applied to queries that can return multiple objects, such as `POST /flow_runs/filter`.""",
    )

    PREFECT_API_MAX_FLOW_RUN_GRAPH_ARTIFACTS: int = Field(
        default=10000,
        description="""Whether or not to enable artifacts on the flow run graph.""",
    )

    PREFECT_API_MAX_FLOW_RUN_GRAPH_NODES: int = Field(
        default=10000,
        description="""The maximum number of artifacts to show on a flow run graph on the v2 API""",
    )

    PREFECT_API_REQUEST_TIMEOUT: float = Field(
        default=60.0, description="""The default timeout for requests to the API"""
    )

    PREFECT_API_SERVICES_CANCELLATION_CLEANUP_ENABLED: bool = Field(
        default=True,
        description="""The maximum size of a flow run graph on the v2 API""",
    )

    PREFECT_API_SERVICES_CANCELLATION_CLEANUP_LOOP_SECONDS: float = Field(
        default=20,
        description="""The cancellation cleanup service will look non-terminal tasks and subflows this often. Defaults to `20`.""",
    )

    PREFECT_API_SERVICES_EVENT_PERSISTER_BATCH_SIZE: int = Field(
        default=20,
        description="""The amount of time to retain events in the database.""",
    )

    PREFECT_API_SERVICES_EVENT_PERSISTER_ENABLED: bool = Field(
        default=True,
        description="""The maximum number of seconds between flushes of the event persister.""",
    )

    PREFECT_API_SERVICES_EVENT_PERSISTER_FLUSH_INTERVAL: float = Field(
        default=5,
        description="""Whether or not to allow streaming events out of via websockets.""",
    )

    PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED: bool = Field(
        default=True,
        description="""Whether or not to start the paused flow run expiration service in the server application. If disabled, paused flows that have timed out will remain in a Paused state until a resume attempt.""",
    )

    PREFECT_API_SERVICES_FOREMAN_DEPLOYMENT_LAST_POLLED_TIMEOUT_SECONDS: int = Field(
        default=60,
        description="""The number of seconds before a work queue is marked as not ready if it has not been polled.""",
    )

    PREFECT_API_SERVICES_FOREMAN_ENABLED: bool = Field(
        default=True,
        description="""Whether or not to start the Foreman service in the server application.""",
    )

    PREFECT_API_SERVICES_FOREMAN_FALLBACK_HEARTBEAT_INTERVAL_SECONDS: int = Field(
        default=30,
        description="""The number of seconds before a deployment is marked as not ready if it has not been polled.""",
    )

    PREFECT_API_SERVICES_FOREMAN_INACTIVITY_HEARTBEAT_MULTIPLE: int = Field(
        default=3,
        description="""The number of seconds to use for online/offline evaluation if a worker's heartbeat interval is not set.""",
    )

    PREFECT_API_SERVICES_FOREMAN_LOOP_SECONDS: float = Field(
        default=15,
        description="""The number of seconds to wait between each iteration of the Foreman loop which checks for offline workers and updates work pool status.""",
    )

    PREFECT_API_SERVICES_FOREMAN_WORK_QUEUE_LAST_POLLED_TIMEOUT_SECONDS: int = Field(
        default=60,
        description="""If `True`, log retryable errors in the API and it's services.""",
    )

    PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS: timedelta = Field(
        default=timedelta(seconds=15),
        description="""The late runs service will mark runs as late after they have exceeded their scheduled start time by this many seconds. Defaults to `5` seconds.""",
    )

    PREFECT_API_SERVICES_LATE_RUNS_ENABLED: bool = Field(
        default=True,
        description="""Whether or not to start the flow run notifications service in the server application. If disabled, you will need to run this service separately to send flow run notifications.""",
    )

    PREFECT_API_SERVICES_LATE_RUNS_LOOP_SECONDS: float = Field(
        default=5,
        description="""The late runs service will look for runs to mark as late this often. Defaults to `5`.""",
    )

    PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_ENABLED: bool = Field(
        default=True,
        description="""The maximum number of characters allowed for a task run cache key. This setting cannot be changed client-side, it must be set on the server.""",
    )

    PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_LOOP_SECONDS: float = Field(
        default=5,
        description="""The pause expiration service will look for runs to mark as failed this often. Defaults to `5`.""",
    )

    PREFECT_API_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE: int = Field(
        default=100,
        description="""The number of deployments the scheduler will attempt to schedule in a single batch. If there are more deployments than the batch size, the scheduler immediately attempts to schedule the next batch; it does not sleep for `scheduler_loop_seconds` until it has visited every deployment once. Defaults to `100`.""",
    )

    PREFECT_API_SERVICES_SCHEDULER_ENABLED: bool = Field(
        default=True,
        description="""Whether or not to start the late runs service in the server application. If disabled, you will need to run this service separately to have runs past their scheduled start time marked as late.""",
    )

    PREFECT_API_SERVICES_SCHEDULER_INSERT_BATCH_SIZE: int = Field(
        default=500,
        description="""The number of flow runs the scheduler will attempt to insert in one batch across all deployments. If the number of flow runs to schedule exceeds this amount, the runs will be inserted in batches of this size. Defaults to `500`.""",
    )

    PREFECT_API_SERVICES_SCHEDULER_LOOP_SECONDS: float = Field(
        default=60,
        description="""The scheduler loop interval, in seconds. This determines how often the scheduler will attempt to schedule new flow runs, but has no impact on how quickly either flow runs or task runs are actually executed. Defaults to `60`.""",
    )

    PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS: int = Field(
        default=100,
        description="""The scheduler will attempt to schedule up to this many auto-scheduled runs in the future. Note that runs may have fewer than this many scheduled runs, depending on the value of `scheduler_max_scheduled_time`. Defaults to `100`.""",
    )

    PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME: timedelta = Field(
        default=timedelta(days=100),
        description="""The scheduler will create new runs up to this far in the future. Note that this setting will take precedence over `scheduler_max_runs`: if a flow runs once a month and `scheduler_max_scheduled_time` is three months, then only three runs will be scheduled. Defaults to 100 days (`8640000` seconds).""",
    )

    PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS: int = Field(
        default=3,
        description="""The scheduler will attempt to schedule at least this many auto-scheduled runs in the future. Note that runs may have more than this many scheduled runs, depending on the value of `scheduler_min_scheduled_time`. Defaults to `3`.""",
    )

    PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME: timedelta = Field(
        default=timedelta(hours=1),
        description="""The scheduler will create new runs at least this far in the future. Note that this setting will take precedence over `scheduler_min_runs`: if a flow runs every hour and `scheduler_min_scheduled_time` is three hours, then three runs will be scheduled even if `scheduler_min_runs` is 1. Defaults to 1 hour (`3600` seconds).""",
    )

    PREFECT_API_SERVICES_TASK_SCHEDULING_ENABLED: bool = Field(
        default=True,
        description="""The `block-type/block-document` slug of a block to use as the default storage for autonomous tasks.""",
    )

    PREFECT_API_SERVICES_TRIGGERS_ENABLED: bool = Field(
        default=True,
        description="""How frequently proactive automations are evaluated""",
    )

    PREFECT_API_SSL_CERT_FILE: Optional[str] = Field(
        default=os.environ.get("SSL_CERT_FILE"),
        description="""This configuration settings option specifies the path to an SSL certificate file. When set, it allows the application to use the specified certificate for secure communication. If left unset, the setting will default to the value provided by the `SSL_CERT_FILE` environment variable.""",
    )

    PREFECT_API_TASK_CACHE_KEY_MAX_LENGTH: int = Field(
        default=2000,
        description="""Whether or not to start the cancellation cleanup service in the server application. If disabled, task runs and subflow runs belonging to cancelled flows may remain in non-terminal states.""",
    )

    PREFECT_API_TLS_INSECURE_SKIP_VERIFY: bool = Field(
        default=False,
        description="""If `True`, disables SSL checking to allow insecure requests. This is recommended only during development, e.g. when using self-signed certificates.""",
    )

    PREFECT_API_URL: Optional[str] = Field(
        default=None,
        description="""If provided, the URL of a hosted Prefect API. Defaults to `None`. When using Prefect Cloud, this will include an account and workspace.""",
    )

    PREFECT_ASYNC_FETCH_STATE_RESULT: bool = Field(
        default=False,
        description="""Determines whether `State.result()` fetches results automatically or not. In Prefect 2.6.0, the `State.result()` method was updated to be async to facilitate automatic retrieval of results from storage which means when writing async code you must `await` the call. For backwards compatibility, the result is not retrieved by default for async users. You may opt into this per call by passing `fetch=True` or toggle this setting to change the behavior globally. This setting does not affect users writing synchronous tasks and flows. This setting does not affect retrieval of results when using `Future.result()`.""",
    )

    PREFECT_CLIENT_CSRF_SUPPORT_ENABLED: bool = Field(
        default=True,
        description="""Determines if CSRF token handling is active in the Prefect client for API requests. When enabled (`True`), the client automatically manages CSRF tokens by retrieving, storing, and including them in applicable state-changing requests (POST, PUT, PATCH, DELETE) to the API. Disabling this setting (`False`) means the client will not handle CSRF tokens, which might be suitable for environments where CSRF protection is disabled. Defaults to `True`, ensuring CSRF protection is enabled by default.""",
    )

    PREFECT_CLIENT_MAX_RETRIES: int = Field(
        default=5,
        description="""The maximum number of retries to perform on failed HTTP requests. Defaults to 5. Set to 0 to disable retries. See `    PREFECT_CLIENT_RETRY_EXTRA_CODES` for details on which HTTP status codes are retried.""",
    )

    PREFECT_CLIENT_RETRY_EXTRA_CODES: str = Field(
        default="",
        description="""A comma-separated list of extra HTTP status codes to retry on. Defaults to an empty string. 429, 502 and 503 are always retried. Please note that not all routes are idempotent and retrying may result in unexpected behavior.""",
    )

    PREFECT_CLIENT_RETRY_JITTER_FACTOR: float = Field(
        default=0.2,
        description="""A value greater than or equal to zero to control the amount of jitter added to retried client requests. Higher values introduce larger amounts of jitter. Set to 0 to disable jitter. See `clamped_poisson_interval` for details on the how jitter can affect retry lengths.""",
    )

    PREFECT_CLI_COLORS: bool = Field(
        default=True,
        description="""If `True`, use colors in CLI output. If `False`, output will not include colors codes. Defaults to `True`.""",
    )

    PREFECT_CLI_PROMPT: Optional[bool] = Field(
        default=None,
        description="""If `True`, use interactive prompts in CLI commands. If `False`, no interactive prompts will be used. If `None`, the value will be dynamically determined based on the presence of an interactive-enabled terminal.""",
    )

    PREFECT_CLI_WRAP_LINES: bool = Field(
        default=True,
        description="""If `True`, wrap text by inserting new lines in long lines in CLI output. If `False`, output will not be wrapped. Defaults to `True`.""",
    )

    PREFECT_CLOUD_API_URL: str = Field(
        default="https://api.prefect.cloud/api",
        description="""API URL for Prefect Cloud. Used for authentication.""",
    )

    PREFECT_CLOUD_UI_URL: Optional[str] = Field(
        default=None,
        description="""The URL for the Cloud UI. By default, this is inferred from the     PREFECT_CLOUD_API_URL. Note:     PREFECT_UI_URL will be workspace specific and will be usable in the open source too. In contrast, this value is only valid for Cloud and will not include the workspace.""",
    )

    PREFECT_DEBUG_MODE: bool = Field(
        default=False,
        description="""If `True`, places the API in debug mode. This may modify behavior to facilitate debugging, including extra logs and other verbose assistance. Defaults to `False`.""",
    )

    PREFECT_DEFAULT_DOCKER_BUILD_NAMESPACE: Optional[str] = Field(
        default=None,
        description="""The directory to serve static files from. This should be used when running into permissions issues when attempting to serve the UI from the default directory (for example when running in a Docker container)""",
    )

    PREFECT_DEFAULT_RESULT_STORAGE_BLOCK: Optional[str] = Field(
        default=None,
        description="""The default Docker namespace to use when building images. Can be either an organization/username or a registry URL with an organization/username.""",
    )

    PREFECT_DEFAULT_WORK_POOL_NAME: Optional[str] = Field(
        default=None,
        description="""The base URL path to serve the Prefect UI from. Defaults to the root path.""",
    )

    PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS: int = Field(
        default=50,
        description="""Number of seconds a worker should wait between sending a heartbeat.""",
    )

    PREFECT_EVENTS_EXPIRED_BUCKET_BUFFER: timedelta = Field(
        default=timedelta(seconds=60),
        description="""Whether or not to start the event persister service in the server application.""",
    )

    PREFECT_EVENTS_MAXIMUM_LABELS_PER_RESOURCE: int = Field(
        default=500,
        description="""The maximum size of an Event when serialized to JSON""",
    )

    PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES: int = Field(
        default=500,
        description="""Whether or not to start the triggers service in the server application.""",
    )

    PREFECT_EVENTS_MAXIMUM_SIZE_BYTES: int = Field(
        default=1_500_000,
        description="""The amount of time to retain expired automation buckets""",
    )

    PREFECT_EVENTS_PROACTIVE_GRANULARITY: timedelta = Field(
        default=timedelta(seconds=5),
        description="""The number of events the event persister will attempt to insert in one batch.""",
    )

    PREFECT_EVENTS_RETENTION_PERIOD: timedelta = Field(
        default=timedelta(days=7),
        description="""How long to cache related resource data for emitting server-side vents""",
    )

    PREFECT_EXPERIMENTAL_DISABLE_SYNC_COMPAT: bool = Field(
        default=False,
        description="""The `block-type/block-document` slug of a block to use as the default result storage.""",
    )

    PREFECT_EXPERIMENTAL_ENABLE_ARTIFACTS_ON_FLOW_RUN_GRAPH: bool = Field(
        default=True,
        description="""Whether or not to enable flow run states on the flow run graph.""",
    )

    PREFECT_EXPERIMENTAL_ENABLE_ENHANCED_CANCELLATION: bool = Field(
        default=True,
        description="""Whether or not to warn when experimental enhanced flow run cancellation is used.""",
    )

    PREFECT_EXPERIMENTAL_ENABLE_EXTRA_RUNNER_ENDPOINTS: bool = Field(
        default=False,
        description="""Whether or not to disable the sync_compatible decorator utility.""",
    )

    PREFECT_EXPERIMENTAL_ENABLE_SCHEDULE_CONCURRENCY: bool = Field(
        default=False, description="""The default work pool to deploy to."""
    )

    PREFECT_EXPERIMENTAL_ENABLE_STATES_ON_FLOW_RUN_GRAPH: bool = Field(
        default=True,
        description="""Whether or not to enable experimental Prefect workers.""",
    )

    PREFECT_EXPERIMENTAL_ENABLE_WORKERS: bool = Field(
        default=True,
        description="""Whether or not to warn when experimental Prefect workers are used.""",
    )

    PREFECT_EXPERIMENTAL_WARN: bool = Field(
        default=True,
        description="""If enabled, warn on usage of experimental features.""",
    )

    PREFECT_EXPERIMENTAL_WARN_ENHANCED_CANCELLATION: bool = Field(
        default=False,
        description="""Maximum number of processes a runner will execute in parallel.""",
    )

    PREFECT_EXPERIMENTAL_WARN_WORKERS: bool = Field(
        default=False,
        description="""Whether or not to enable experimental enhanced flow run cancellation.""",
    )

    PREFECT_EXTRA_ENTRYPOINTS: str = Field(
        default="",
        description="""Modules for Prefect to import when Prefect is imported. Values should be separated by commas, e.g. `my_module,my_other_module`. Objects within modules may be specified by a ':' partition, e.g. `my_module:my_object`. If a callable object is provided, it will be called with no arguments on import.""",
    )

    PREFECT_FLOW_DEFAULT_RETRIES: int = Field(
        default=0,
        description="""This value sets the default number of retries for all flows. This value does not overwrite individually set retries values on a flow""",
    )

    PREFECT_FLOW_DEFAULT_RETRY_DELAY_SECONDS: Union[int, float] = Field(
        default=0,
        description="""This value sets the retry delay seconds for all flows. This value does not overwrite individually set retry delay seconds""",
    )

    PREFECT_HOME: Annotated[Path, AfterValidator(lambda x: x.expanduser())] = Field(
        default=Path("~"),
        description="""Prefect's home directory. Defaults to `~/.prefect`. This directory may be created automatically when required.""",
    )

    PREFECT_LOCAL_STORAGE_PATH: Path = Field(
        default=Path("${PREFECT_HOME}"),
        description="""The path to a block storage directory to store things in.""",
    )

    PREFECT_LOGGING_COLORS: bool = Field(
        default=True, description="""Whether to style console logs with color."""
    )

    PREFECT_LOGGING_EXTRA_LOGGERS: str = Field(
        default="",
        description="""Additional loggers to attach to Prefect logging at runtime. Values should be comma separated. The handlers attached to the 'prefect' logger will be added to these loggers. Additionally, if the level is not set, it will be set to the same level as the 'prefect' logger.""",
    )

    PREFECT_LOGGING_INTERNAL_LEVEL: str = Field(
        default="ERROR",
        description="""The default logging level for Prefect's internal machinery loggers. Defaults to "ERROR" during normal operation. Is forced to "DEBUG" during debug mode.""",
    )

    PREFECT_LOGGING_LEVEL: str = Field(
        default="INFO",
        description="""The default logging level for Prefect loggers. Defaults to "INFO" during normal operation. Is forced to "DEBUG" during debug mode.""",
    )

    PREFECT_LOGGING_LOG_PRINTS: bool = Field(
        default=False,
        description="""If set, `print` statements in flows and tasks will be redirected to the Prefect logger for the given run. This setting can be overridden by individual tasks and flows.""",
    )

    PREFECT_LOGGING_MARKUP: bool = Field(
        default=False,
        description="""Whether to interpret strings wrapped in square brackets as a style. This allows styles to be conveniently added to log messages, e.g. `[red]This is a red message.[/red]`. However, the downside is, if enabled, strings that contain square brackets may be inaccurately interpreted and lead to incomplete output, e.g. `DROP TABLE [dbo].[SomeTable];"` outputs `DROP TABLE .[SomeTable];`.""",
    )

    PREFECT_LOGGING_SERVER_LEVEL: str = Field(
        default="WARNING",
        description="""The default logging level for the Prefect API server.""",
    )

    PREFECT_LOGGING_SETTINGS_PATH: Path = Field(
        default=Path("${PREFECT_HOME}"),
        description="""The path to a custom YAML logging configuration file. If no file is found, the default `logging.yml` is used. Defaults to a logging.yml in the Prefect home directory.""",
    )

    PREFECT_LOGGING_TO_API_BATCH_INTERVAL: float = Field(
        default=2.0,
        description="""The number of seconds between batched writes of logs to the API.""",
    )

    PREFECT_LOGGING_TO_API_BATCH_SIZE: int = Field(
        default=4_000_000,
        description="""The maximum size in bytes for a batch of logs.""",
    )

    PREFECT_LOGGING_TO_API_ENABLED: bool = Field(
        default=True,
        description="""Toggles sending logs to the API. If `False`, logs sent to the API log handler will not be sent to the API.""",
    )

    PREFECT_LOGGING_TO_API_MAX_LOG_SIZE: int = Field(
        default=1_000_000, description="""The maximum size in bytes for a single log."""
    )

    PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW: Literal["warn"] = Field(
        default="warn",
        description="""Controls the behavior when loggers attempt to send logs to the API handler from outside of a flow. All logs sent to the API must be associated with a flow run. The API log handler can only be used outside of a flow by manually providing a flow run identifier. Logs that are not associated with a flow run will not be sent to the API. This setting can be used to determine if a warning or error is displayed when the identifier is missing. The following options are available: - "warn": Log a warning message. - "error": Raise an error. - "ignore": Do not log a warning message or raise an error.""",
    )

    PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION: bool = Field(
        default=True,
        description="""Controls whether or not block auto-registration on start up should be memoized. Setting to False may result in slower server start up times.""",
    )

    PREFECT_MEMO_STORE_PATH: Path = Field(
        default=Path("${PREFECT_HOME}"),
        description="""The path to the memo store file.""",
    )

    PREFECT_MESSAGING_BROKER: str = Field(
        default="prefect.server.utilities.messaging.memory",
        description="""The maximum number of labels a resource may have.""",
    )

    PREFECT_MESSAGING_CACHE: str = Field(
        default="prefect.server.utilities.messaging.memory",
        description="""The maximum number of related resources an Event may have.""",
    )

    PREFECT_PROFILES_PATH: Path = Field(
        default=Path("${PREFECT_HOME}"),
        description="""The path to a profiles configuration files.""",
    )

    PREFECT_RESULTS_DEFAULT_SERIALIZER: str = Field(
        default="pickle",
        description="""The default serializer to use when not otherwise specified.""",
    )

    PREFECT_RESULTS_PERSIST_BY_DEFAULT: bool = Field(
        default=False,
        description="""The default setting for persisting results when not otherwise specified. If enabled, flow and task results will be persisted unless they opt out.""",
    )

    PREFECT_RUNNER_POLL_FREQUENCY: int = Field(
        default=10,
        description="""Number of missed polls before a runner is considered unhealthy by its webserver.""",
    )

    PREFECT_RUNNER_PROCESS_LIMIT: int = Field(
        default=5,
        description="""Number of seconds a runner should wait between queries for scheduled work.""",
    )

    PREFECT_RUNNER_SERVER_ENABLE: bool = Field(
        default=False,
        description="""The maximum number of scheduled runs to create for a deployment.""",
    )

    PREFECT_RUNNER_SERVER_HOST: str = Field(
        default="localhost",
        description="""The port the runner's webserver should bind to.""",
    )

    PREFECT_RUNNER_SERVER_LOG_LEVEL: str = Field(
        default="error",
        description="""Whether or not to enable the runner's webserver.""",
    )

    PREFECT_RUNNER_SERVER_MISSED_POLLS_TOLERANCE: int = Field(
        default=2,
        description="""The host address the runner's webserver should bind to.""",
    )

    PREFECT_RUNNER_SERVER_PORT: int = Field(
        default=8080, description="""The log level of the runner's webserver."""
    )

    PREFECT_SERVER_ANALYTICS_ENABLED: bool = Field(
        default=True,
        description="""Whether or not to start the scheduling service in the server application. If disabled, you will need to run this service separately to schedule runs for deployments.""",
    )

    PREFECT_SERVER_API_HOST: str = Field(
        default="127.0.0.1",
        description="""The API's port address (defaults to `4200`).""",
    )

    PREFECT_SERVER_API_KEEPALIVE_TIMEOUT: int = Field(
        default=5,
        description="""Controls the activation of CSRF protection for the Prefect server API. When enabled (`True`), the server enforces CSRF validation checks on incoming state-changing requests (POST, PUT, PATCH, DELETE), requiring a valid CSRF token to be included in the request headers or body. This adds a layer of security by preventing unauthorized or malicious sites from making requests on behalf of authenticated users. It is recommended to enable this setting in production environments where the API is exposed to web clients to safeguard against CSRF attacks. Note: Enabling this setting requires corresponding support in the client for CSRF token management. See     PREFECT_CLIENT_CSRF_SUPPORT_ENABLED for more.""",
    )

    PREFECT_SERVER_API_PORT: int = Field(
        default=4200,
        description="""The API's keep alive timeout (defaults to `5`). Refer to https://www.uvicorn.org/settings/#timeouts for details. When the API is hosted behind a load balancer, you may want to set this to a value greater than the load balancer's idle timeout. Note this setting only applies when calling `prefect server start`; if hosting the API with another tool you will need to configure this there instead.""",
    )

    PREFECT_SERVER_CSRF_PROTECTION_ENABLED: bool = Field(
        default=False,
        description="""Specifies the duration for which a CSRF token remains valid after being issued by the server. The default expiration time is set to 1 hour, which offers a reasonable compromise. Adjust this setting based on your specific security requirements and usage patterns.""",
    )

    PREFECT_SERVER_CSRF_TOKEN_EXPIRATION: timedelta = Field(
        default=timedelta(hours=1),
        description="""Whether or not to serve the Prefect UI.""",
    )

    PREFECT_SILENCE_API_URL_MISCONFIGURATION: bool = Field(
        default=False,
        description="""If `True`, disable the warning when a user accidentally misconfigure its `    PREFECT_API_URL` Sometimes when a user manually set `    PREFECT_API_URL` to a custom url,reverse-proxy for example, we would like to silence this warning so we will set it to `FALSE`.""",
    )

    PREFECT_SQLALCHEMY_MAX_OVERFLOW: Optional[int] = Field(
        default=None,
        description="""Controls maximum overflow of the connection pool when using a PostgreSQL database with the Prefect API. If not set, the default SQLAlchemy maximum overflow value will be used.""",
    )

    PREFECT_SQLALCHEMY_POOL_SIZE: Optional[int] = Field(
        default=None,
        description="""Controls connection pool size when using a PostgreSQL database with the Prefect API. If not set, the default SQLAlchemy pool size will be used.""",
    )

    PREFECT_TASKS_REFRESH_CACHE: bool = Field(
        default=False,
        description="""If `True`, enables a refresh of cached results: re-executing the task will refresh the cached results. Defaults to `False`.""",
    )

    PREFECT_TASK_DEFAULT_RETRIES: int = Field(
        default=0,
        description="""This value sets the default number of retries for all tasks. This value does not overwrite individually set retries values on tasks""",
    )

    PREFECT_TASK_DEFAULT_RETRY_DELAY_SECONDS: Union[float, int, list[float]] = Field(
        default=0,
        description="""This value sets the default retry delay seconds for all tasks. This value does not overwrite individually set retry delay seconds""",
    )

    PREFECT_TASK_RUN_TAG_CONCURRENCY_SLOT_WAIT_SECONDS: int = Field(
        default=30,
        description="""The number of seconds to wait before retrying when a task run cannot secure a concurrency slot from the server.""",
    )

    PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK: str = Field(
        default="local-file-system/prefect-task-scheduling",
        description="""Whether or not to delete failed task submissions from the database.""",
    )

    PREFECT_TASK_SCHEDULING_DELETE_FAILED_SUBMISSIONS: bool = Field(
        default=True,
        description="""The maximum number of scheduled tasks to queue for submission.""",
    )

    PREFECT_TASK_SCHEDULING_MAX_RETRY_QUEUE_SIZE: int = Field(
        default=100,
        description="""How long before a PENDING task are made available to another task worker. In practice, a task worker should move a task from PENDING to RUNNING very quickly, so runs stuck in PENDING for a while is a sign that the task worker may have crashed.""",
    )

    PREFECT_TASK_SCHEDULING_MAX_SCHEDULED_QUEUE_SIZE: int = Field(
        default=1000,
        description="""The maximum number of retries to queue for submission.""",
    )

    PREFECT_TASK_SCHEDULING_PENDING_TASK_TIMEOUT: timedelta = Field(
        default=timedelta(0),
        description="""Whether or not to enable experimental worker webserver endpoints.""",
    )

    PREFECT_TEST_MODE: bool = Field(
        default=False,
        description="""If `True`, places the API in test mode. This may modify behavior to facilitate testing. Defaults to `False`.""",
    )

    PREFECT_TEST_SETTING: Any = Field(
        default=None,
        description="""This variable only exists to facilitate testing of settings. If accessed when `    PREFECT_TEST_MODE` is not set, `None` is returned.""",
    )

    PREFECT_UI_API_URL: Optional[str] = Field(
        default=None,
        description="""When enabled, Prefect sends anonymous data (e.g. count of flow runs, package version) on server startup to help us improve our product.""",
    )

    PREFECT_UI_ENABLED: bool = Field(
        default=True,
        description="""The connection url for communication from the UI to the API. Defaults to `    PREFECT_API_URL` if set. Otherwise, the default URL is generated from `    PREFECT_SERVER_API_HOST` and `    PREFECT_SERVER_API_PORT`. If providing a custom value, the aforementioned settings may be templated into the given string.""",
    )

    PREFECT_UI_SERVE_BASE: str = Field(
        default="/",
        description="""Which message broker implementation to use for the messaging system, should point to a module that exports a Publisher and Consumer class.""",
    )

    PREFECT_UI_STATIC_DIRECTORY: Optional[str] = Field(
        default=None,
        description="""Which cache implementation to use for the events system. Should point to a module that exports a Cache class.""",
    )

    PREFECT_UI_URL: Optional[str] = Field(
        default=None,
        description="""The URL for the UI. By default, this is inferred from the     PREFECT_API_URL. When using Prefect Cloud, this will include the account and workspace. When using an ephemeral server, this will be `None`.""",
    )

    PREFECT_UNIT_TEST_LOOP_DEBUG: bool = Field(
        default=True,
        description="""If `True` turns on debug mode for the unit testing event loop. Defaults to `False`.""",
    )

    PREFECT_UNIT_TEST_MODE: bool = Field(
        default=False,
        description="""This variable only exists to facilitate unit testing. If `True`, code is executing in a unit test context. Defaults to `False`.""",
    )

    PREFECT_WORKER_HEARTBEAT_SECONDS: float = Field(
        default=30,
        description="""Number of seconds a worker should wait between queries for scheduled flow runs.""",
    )

    PREFECT_WORKER_PREFETCH_SECONDS: float = Field(
        default=10,
        description="""The host address the worker's webserver should bind to.""",
    )

    PREFECT_WORKER_QUERY_SECONDS: float = Field(
        default=10,
        description="""The number of seconds into the future a worker should query for scheduled flow runs. Can be used to compensate for infrastructure start up time for a worker.""",
    )

    PREFECT_WORKER_WEBSERVER_HOST: str = Field(
        default="0.0.0.0",
        description="""The port the worker's webserver should bind to.""",
    )

    PREFECT_WORKER_WEBSERVER_PORT: int = Field(
        default=8080,
        description="""Whether or not to start the task scheduling service in the server application.""",
    )
