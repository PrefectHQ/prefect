"""
Prefect settings. Settings objects are Pydantic `BaseSettings` models for typed
configuration via environment variables. For organization, they are grouped into
multiple settings classes that are nested and can all be accessed from the main
settings object, `Settings()`. 
"""
# Note that when implementing nested settings, a `default_factory` should be
# used to avoid instantiating the nested settings class until runtime.

import textwrap
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseSettings, Field, SecretStr
from typing import Optional
from pydantic.fields import Undefined


class SharedSettings(BaseSettings):
    """
    These settings represent values that are likely to be interpolated into
    other settings, stored in a separate class for eager instantiation.

    To change these settings via environment variable, set
    `PREFECT_{SETTING}=X`.
    """

    class Config:
        env_prefix = "PREFECT_"
        frozen = True

    home: Path = Field(
        Path("~/.prefect").expanduser(),
        description="Prefect's home directory. Defaults to `~/.prefect`.",
    )

    debug_mode: bool = Field(
        False,
        description="If `True`, places the API in debug mode. This may modify behavior to facilitate debugging. Defaults to `False`.",
    )
    test_mode: bool = Field(
        False,
        description="If `True`, places the API in test mode. This may modify behavior to faciliate testing. Defaults to `False`.",
    )


# instantiate the shared settings
shared_settings = SharedSettings()


class DataLocationSettings(BaseSettings):
    """Settings related to the Orion Data API. To change these settings via
    environment variable, set `PREFECT_ORION_DATA_{SETTING}=X`."""

    class Config:
        env_prefix = "PREFECT_ORION_DATA_"
        frozen = True

    name: str = Field(
        "default",
        description="The name for the default data directory. Defaults to `default`.",
    )
    scheme: str = Field(
        "file",
        description="The scheme for the default data directory. Defaults to `file`.",
    )
    base_path: str = Field(
        "/tmp",
        description="The base path for the default data directory. Defaults to `/tmp`.",
    )


class DatabaseSettings(BaseSettings):
    """Settings related to the Orion database. To change these settings via
    environment variable, set `PREFECT_ORION_DATABASE_{SETTING}=X`."""

    class Config:
        env_prefix = "PREFECT_ORION_DATABASE_"
        frozen = True

    connection_url: SecretStr = Field(
        f"sqlite+aiosqlite:////{shared_settings.home}/orion.db",
        description=textwrap.dedent(
            f"""
            A database connection URL in a SQLAlchemy-compatible
            format. Orion currently supports SQLite and Postgres. Note that all
            Orion engines must use an async driver - for SQLite, use
            `sqlite+aiosqlite` and for Postgres use `postgresql+asyncpg`. 

            SQLite in-memory databases can be used by providing the url
            `sqlite+aiosqlite:///file::memory:?cache=shared&uri=true&check_same_thread=false`,
            which will allow the database to be accessed by multiple threads. Note
            that in-memory databases can not be accessed from multiple processes and
            should only be used for simple tests.

            Defaults to `sqlite+aiosqlite:////{shared_settings.home}/orion.db`.
            """
        ),
    )
    echo: bool = Field(
        False,
        description="If `True`, SQLAlchemy will log all SQL issued to the database. Defaults to `False`.",
    )

    timeout: Optional[float] = Field(
        1,
        description="""A statement timeout, in seconds, applied to all database
        interactions made by the API. Defaults to `1`.""",
    )


class APISettings(BaseSettings):
    """Settings related to the Orion API. To change these settings via
    environment variable, set `PREFECT_ORION_API_{SETTING}=X`.
    """

    # a default limit for queries
    default_limit: int = Field(
        200,
        description="""The default limit applied to queries that can return
        multiple objects, such as `POST /flow_runs/filter`.""",
    )

    host: str = Field(
        "127.0.0.1",
        description="""The API's host address (defaults to `127.0.0.1`).""",
    )
    port: int = Field(
        4200,
        description="""The API's port address (defaults to `4200`).""",
    )

    uvicorn_log_level: str = Field(
        "info", description="The uvicorn log level (defaults to `info`)."
    )


class ServicesSettings(BaseSettings):
    """Settings related to Orion services. To change these settings via
    environment variable, set `PREFECT_ORION_SERVICES_{SETTING}=X`.
    """

    class Config:
        env_prefix = "PREFECT_ORION_SERVICES_"
        frozen = True

    run_in_app: bool = Field(
        False,
        description="""If `True`, Orion services are started as part of the
        webserver and run in the same event loop. Defaults to `False`.""",
    )

    # -- Scheduler

    scheduler_loop_seconds: float = Field(
        60,
        description="""The scheduler loop interval, in seconds. This determines
        how often the scheduler will attempt to schedule new flow runs, but has
        no impact on how quickly either flow runs or task runs are actually
        executed. Creating new deployments or schedules will always create new
        flow runs optimistically, without waiting for the scheduler. Defaults to
        `60`.""",
    )

    scheduler_deployment_batch_size: int = Field(
        100,
        description="""The number of deployments the scheduler will attempt to
        schedule in a single batch. If there are more deployments than the batch
        size, the scheduler immediately attempts to schedule the next batch; it
        does not sleep for `scheduler_loop_seconds` until it has visited every
        deployment once. Defaults to `100`.""",
    )

    scheduler_max_runs: int = Field(
        100,
        description="""The scheduler will attempt to schedule up to this many
        auto-scheduled runs in the future. Note that runs may have fewer than
        this many scheduled runs, depending on the value of
        `scheduler_max_scheduled_time`.  Defaults to `100`.
        """,
    )

    scheduler_max_scheduled_time: timedelta = Field(
        timedelta(days=100),
        description="""The scheduler will create new runs up to this far in the
        future. Note that this setting will take precedence over
        `scheduler_max_runs`: if a flow runs once a month and
        `scheduled_max_scheduled_time` is three months, then only three runs will be
        scheduled. Defaults to 100 days (`8640000` seconds).
        """,
    )

    scheduler_insert_batch_size: int = Field(
        500,
        description="""The number of flow runs the scheduler will attempt to insert 
        in one batch across all deployments. If the number of flow runs to 
        schedule exceeds this amount, the runs will be inserted in batches of this size. Defaults to `500`.
        """,
    )

    # -- Agent

    # check for new runs every X seconds
    agent_loop_seconds: float = Field(
        5,
        description="""The agent loop interval, in seconds. Agents will check
        for new runs this often. Defaults to `5`.""",
    )
    # check for runs that are scheduled to start in the next X seconds
    agent_prefetch_seconds: int = Field(
        10,
        description="""Agents will look for scheduled runs this many seconds in
        the future and attempt to run them. This accounts for any additional
        infrastructure spin-up time or latency in preparing a flow run. Note
        flow runs will not start before their scheduled time, even if they are
        prefetched. Defaults to `10`.""",
    )

    # -- Late Runs

    # check for late runs every 5 seconds
    late_runs_loop_seconds: float = Field(
        5,
        description="""The late runs service will look for runs to mark as late
        this often. Defaults to `5`.""",
    )
    # mark runs if they are 5 seconds late
    mark_late_after: timedelta = Field(
        timedelta(seconds=5),
        description="""The late runs service will mark runs as late after they
        have exceeded their scheduled start time by this many seconds. Defaults
        to `5` seconds.""",
    )


class OrionSettings(BaseSettings):
    """Settings related to Orion. To change these settings via environment variable, set
    `PREFECT_ORION_{SETTING}=X`.
    """

    class Config:
        env_prefix = "PREFECT_ORION_"
        frozen = True

    database: DatabaseSettings = Field(
        default_factory=DatabaseSettings,
        description="Nested [Database settings][prefect.utilities.settings.DatabaseSettings].",
    )
    data: DataLocationSettings = Field(
        default_factory=DataLocationSettings,
        description="Nested [Data settings][prefect.utilities.settings.DataSettings].",
    )
    api: APISettings = Field(
        default_factory=APISettings,
        description="Nested [API settings][prefect.utilities.settings.APISettings].",
    )
    services: ServicesSettings = Field(
        default_factory=ServicesSettings,
        description="Nested [Services settings][prefect.utilities.settings.ServicesSettings].",
    )


class LoggingSettings(BaseSettings):
    """Settings related to Orion services. To change these settings via environment variable, set
    `PREFECT_LOGGING_{SETTING}=X`.
    """

    class Config:
        env_prefix = "PREFECT_LOGGING_"
        frozen = True

    settings_path: Path = Field(
        Path(f"{shared_settings.home}/logging.yml"),
        description=f"""The path to a logging configuration file. Defaults to
        `{shared_settings.home}/logging.yml`.""",
    )


class Settings(SharedSettings):
    """Global Prefect settings. To change these settings via environment variable, set
    `PREFECT_{SETTING}=X`.
    """

    # note: incorporates all settings from the PrefectSettings class

    # logging
    logging: LoggingSettings = Field(
        default_factory=LoggingSettings,
        description="Nested [Logging settings][prefect.utilities.settings.LoggingSettings].",
    )

    # orion
    orion: OrionSettings = Field(
        default_factory=OrionSettings,
        description="Nested [Orion settings][prefect.utilities.settings.OrionSettings].",
    )

    # the connection url for an orion instance
    orion_host: str = Field(
        None,
        description="""If provided, the url of an externally-hosted Orion API.
        Defaults to `None`.""",
    )


settings = Settings()
