from datetime import timedelta
from typing import ClassVar

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class ServicesBaseSetting(PrefectBaseSettings):
    enabled: bool = Field(
        default=True,
        description="Whether or not to start the service in the server application.",
    )


class ServerServicesCancellationCleanupSettings(ServicesBaseSetting):
    """
    Settings for controlling the cancellation cleanup service
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "services", "cancellation_cleanup")
    )

    enabled: bool = Field(
        default=True,
        description="Whether or not to start the cancellation cleanup service in the server application.",
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_server_services_cancellation_cleanup_enabled",
            "prefect_api_services_cancellation_cleanup_enabled",
        ),
    )

    loop_seconds: float = Field(
        default=20,
        description="The cancellation cleanup service will look for non-terminal tasks and subflows this often. Defaults to `20`.",
        validation_alias=AliasChoices(
            AliasPath("loop_seconds"),
            "prefect_server_services_cancellation_cleanup_loop_seconds",
            "prefect_api_services_cancellation_cleanup_loop_seconds",
        ),
    )


class ServerServicesEventPersisterSettings(ServicesBaseSetting):
    """
    Settings for controlling the event persister service
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "services", "event_persister")
    )

    enabled: bool = Field(
        default=True,
        description="Whether or not to start the event persister service in the server application.",
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_server_services_event_persister_enabled",
            "prefect_api_services_event_persister_enabled",
        ),
    )

    batch_size: int = Field(
        default=20,
        gt=0,
        description="The number of events the event persister will attempt to insert in one batch.",
        validation_alias=AliasChoices(
            AliasPath("batch_size"),
            "prefect_server_services_event_persister_batch_size",
            "prefect_api_services_event_persister_batch_size",
        ),
    )

    flush_interval: float = Field(
        default=5,
        gt=0.0,
        description="The maximum number of seconds between flushes of the event persister.",
        validation_alias=AliasChoices(
            AliasPath("flush_interval"),
            "prefect_server_services_event_persister_flush_interval",
            "prefect_api_services_event_persister_flush_interval",
        ),
    )

    batch_size_delete: int = Field(
        default=10_000,
        gt=0,
        description="The number of expired events and event resources the event persister will attempt to delete in one batch.",
        validation_alias=AliasChoices(
            AliasPath("batch_size_delete"),
            "prefect_server_services_event_persister_batch_size_delete",
        ),
    )


class ServerServicesEventLoggerSettings(ServicesBaseSetting):
    """
    Settings for controlling the event logger service
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "services", "event_logger")
    )

    enabled: bool = Field(
        default=False,
        description="Whether or not to start the event logger service in the server application.",
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_server_services_event_logger_enabled",
            "prefect_api_services_event_logger_enabled",
        ),
    )


class ServerServicesForemanSettings(ServicesBaseSetting):
    """
    Settings for controlling the foreman service
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "services", "foreman")
    )

    enabled: bool = Field(
        default=True,
        description="Whether or not to start the foreman service in the server application.",
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_server_services_foreman_enabled",
            "prefect_api_services_foreman_enabled",
        ),
    )

    loop_seconds: float = Field(
        default=15,
        description="The foreman service will check for offline workers this often. Defaults to `15`.",
        validation_alias=AliasChoices(
            AliasPath("loop_seconds"),
            "prefect_server_services_foreman_loop_seconds",
            "prefect_api_services_foreman_loop_seconds",
        ),
    )

    inactivity_heartbeat_multiple: int = Field(
        default=3,
        description="""
        The number of heartbeats that must be missed before a worker is marked as offline. Defaults to `3`.
        """,
        validation_alias=AliasChoices(
            AliasPath("inactivity_heartbeat_multiple"),
            "prefect_server_services_foreman_inactivity_heartbeat_multiple",
            "prefect_api_services_foreman_inactivity_heartbeat_multiple",
        ),
    )

    fallback_heartbeat_interval_seconds: int = Field(
        default=30,
        description="""
        The number of seconds to use for online/offline evaluation if a worker's heartbeat
        interval is not set. Defaults to `30`.
        """,
        validation_alias=AliasChoices(
            AliasPath("fallback_heartbeat_interval_seconds"),
            "prefect_server_services_foreman_fallback_heartbeat_interval_seconds",
            "prefect_api_services_foreman_fallback_heartbeat_interval_seconds",
        ),
    )

    deployment_last_polled_timeout_seconds: int = Field(
        default=60,
        description="""
        The number of seconds before a deployment is marked as not ready if it has not been
        polled. Defaults to `60`.
        """,
        validation_alias=AliasChoices(
            AliasPath("deployment_last_polled_timeout_seconds"),
            "prefect_server_services_foreman_deployment_last_polled_timeout_seconds",
            "prefect_api_services_foreman_deployment_last_polled_timeout_seconds",
        ),
    )

    work_queue_last_polled_timeout_seconds: int = Field(
        default=60,
        description="""
        The number of seconds before a work queue is marked as not ready if it has not been
        polled. Defaults to `60`.
        """,
        validation_alias=AliasChoices(
            AliasPath("work_queue_last_polled_timeout_seconds"),
            "prefect_server_services_foreman_work_queue_last_polled_timeout_seconds",
            "prefect_api_services_foreman_work_queue_last_polled_timeout_seconds",
        ),
    )


class ServerServicesLateRunsSettings(ServicesBaseSetting):
    """
    Settings for controlling the late runs service
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "services", "late_runs")
    )

    enabled: bool = Field(
        default=True,
        description="Whether or not to start the late runs service in the server application.",
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_server_services_late_runs_enabled",
            "prefect_api_services_late_runs_enabled",
        ),
    )

    loop_seconds: float = Field(
        default=5,
        description="""
        The late runs service will look for runs to mark as late this often. Defaults to `5`.
        """,
        validation_alias=AliasChoices(
            AliasPath("loop_seconds"),
            "prefect_server_services_late_runs_loop_seconds",
            "prefect_api_services_late_runs_loop_seconds",
        ),
    )

    after_seconds: timedelta = Field(
        default=timedelta(seconds=15),
        description="""
        The late runs service will mark runs as late after they have exceeded their scheduled start time by this many seconds. Defaults to `5` seconds.
        """,
        validation_alias=AliasChoices(
            AliasPath("after_seconds"),
            "prefect_server_services_late_runs_after_seconds",
            "prefect_api_services_late_runs_after_seconds",
        ),
    )


class ServerServicesSchedulerSettings(ServicesBaseSetting):
    """
    Settings for controlling the scheduler service
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "services", "scheduler")
    )

    enabled: bool = Field(
        default=True,
        description="Whether or not to start the scheduler service in the server application.",
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_server_services_scheduler_enabled",
            "prefect_api_services_scheduler_enabled",
        ),
    )

    loop_seconds: float = Field(
        default=60,
        description="""
        The scheduler loop interval, in seconds. This determines
        how often the scheduler will attempt to schedule new flow runs, but has no
        impact on how quickly either flow runs or task runs are actually executed.
        Defaults to `60`.
        """,
        validation_alias=AliasChoices(
            AliasPath("loop_seconds"),
            "prefect_server_services_scheduler_loop_seconds",
            "prefect_api_services_scheduler_loop_seconds",
        ),
    )

    deployment_batch_size: int = Field(
        default=100,
        description="""
        The number of deployments the scheduler will attempt to
        schedule in a single batch. If there are more deployments than the batch
        size, the scheduler immediately attempts to schedule the next batch; it
        does not sleep for `scheduler_loop_seconds` until it has visited every
        deployment once. Defaults to `100`.
        """,
        validation_alias=AliasChoices(
            AliasPath("deployment_batch_size"),
            "prefect_server_services_scheduler_deployment_batch_size",
            "prefect_api_services_scheduler_deployment_batch_size",
        ),
    )

    max_runs: int = Field(
        default=100,
        description="""
        The scheduler will attempt to schedule up to this many
        auto-scheduled runs in the future. Note that runs may have fewer than
        this many scheduled runs, depending on the value of
        `scheduler_max_scheduled_time`.  Defaults to `100`.
        """,
        validation_alias=AliasChoices(
            AliasPath("max_runs"),
            "prefect_server_services_scheduler_max_runs",
            "prefect_api_services_scheduler_max_runs",
        ),
    )

    min_runs: int = Field(
        default=3,
        description="""
        The scheduler will attempt to schedule at least this many
        auto-scheduled runs in the future. Note that runs may have more than
        this many scheduled runs, depending on the value of
        `scheduler_min_scheduled_time`.  Defaults to `3`.
        """,
        validation_alias=AliasChoices(
            AliasPath("min_runs"),
            "prefect_server_services_scheduler_min_runs",
            "prefect_api_services_scheduler_min_runs",
        ),
    )

    max_scheduled_time: timedelta = Field(
        default=timedelta(days=100),
        description="""
        The scheduler will create new runs up to this far in the
        future. Note that this setting will take precedence over
        `scheduler_max_runs`: if a flow runs once a month and
        `scheduler_max_scheduled_time` is three months, then only three runs will be
        scheduled. Defaults to 100 days (`8640000` seconds).
        """,
        validation_alias=AliasChoices(
            AliasPath("max_scheduled_time"),
            "prefect_server_services_scheduler_max_scheduled_time",
            "prefect_api_services_scheduler_max_scheduled_time",
        ),
    )

    min_scheduled_time: timedelta = Field(
        default=timedelta(hours=1),
        description="""
        The scheduler will create new runs at least this far in the
        future. Note that this setting will take precedence over `scheduler_min_runs`:
        if a flow runs every hour and `scheduler_min_scheduled_time` is three hours,
        then three runs will be scheduled even if `scheduler_min_runs` is 1. Defaults to
        """,
        validation_alias=AliasChoices(
            AliasPath("min_scheduled_time"),
            "prefect_server_services_scheduler_min_scheduled_time",
            "prefect_api_services_scheduler_min_scheduled_time",
        ),
    )

    insert_batch_size: int = Field(
        default=500,
        description="""
        The number of runs the scheduler will attempt to insert in a single batch.
        Defaults to `500`.
        """,
        validation_alias=AliasChoices(
            AliasPath("insert_batch_size"),
            "prefect_server_services_scheduler_insert_batch_size",
            "prefect_api_services_scheduler_insert_batch_size",
        ),
    )

    recent_deployments_loop_seconds: float = Field(
        default=5,
        description="""
        The number of seconds the recent deployments scheduler will wait between checking for recently updated deployments. Defaults to `5`.
        """,
    )


class ServerServicesPauseExpirationsSettings(ServicesBaseSetting):
    """
    Settings for controlling the pause expiration service
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "services", "pause_expirations")
    )

    enabled: bool = Field(
        default=True,
        description="""
        Whether or not to start the paused flow run expiration service in the server
        application. If disabled, paused flows that have timed out will remain in a Paused state
        until a resume attempt.
        """,
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_server_services_pause_expirations_enabled",
            "prefect_api_services_pause_expirations_enabled",
        ),
    )

    loop_seconds: float = Field(
        default=5,
        description="""
        The pause expiration service will look for runs to mark as failed this often. Defaults to `5`.
        """,
        validation_alias=AliasChoices(
            AliasPath("loop_seconds"),
            "prefect_server_services_pause_expirations_loop_seconds",
            "prefect_api_services_pause_expirations_loop_seconds",
        ),
    )


class ServerServicesRepossessorSettings(ServicesBaseSetting):
    """
    Settings for controlling the repossessor service
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "services", "repossessor")
    )

    enabled: bool = Field(
        default=True,
        description="Whether or not to start the repossessor service in the server application.",
    )

    loop_seconds: float = Field(
        default=15,
        description="The repossessor service will look for expired leases this often. Defaults to `15`.",
    )


class ServerServicesTaskRunRecorderSettings(ServicesBaseSetting):
    """
    Settings for controlling the task run recorder service
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "services", "task_run_recorder")
    )

    enabled: bool = Field(
        default=True,
        description="Whether or not to start the task run recorder service in the server application.",
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_server_services_task_run_recorder_enabled",
            "prefect_api_services_task_run_recorder_enabled",
        ),
    )


class ServerServicesTriggersSettings(ServicesBaseSetting):
    """
    Settings for controlling the triggers service
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "services", "triggers")
    )

    enabled: bool = Field(
        default=True,
        description="Whether or not to start the triggers service in the server application.",
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_server_services_triggers_enabled",
            "prefect_api_services_triggers_enabled",
        ),
    )

    pg_notify_reconnect_interval_seconds: int = Field(
        default=10,
        description="""
        The number of seconds to wait before reconnecting to the PostgreSQL NOTIFY/LISTEN 
        connection after an error. Only used when using PostgreSQL as the database.
        Defaults to `10`.
        """,
        validation_alias=AliasChoices(
            AliasPath("pg_notify_reconnect_interval_seconds"),
            "prefect_server_services_triggers_pg_notify_reconnect_interval_seconds",
        ),
    )

    pg_notify_heartbeat_interval_seconds: int = Field(
        default=5,
        description="""
        The number of seconds between heartbeat checks for the PostgreSQL NOTIFY/LISTEN 
        connection to ensure it's still alive. Only used when using PostgreSQL as the database.
        Defaults to `5`.
        """,
        validation_alias=AliasChoices(
            AliasPath("pg_notify_heartbeat_interval_seconds"),
            "prefect_server_services_triggers_pg_notify_heartbeat_interval_seconds",
        ),
    )


class ServerServicesSettings(PrefectBaseSettings):
    """
    Settings for controlling server services
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "services")
    )

    cancellation_cleanup: ServerServicesCancellationCleanupSettings = Field(
        default_factory=ServerServicesCancellationCleanupSettings,
        description="Settings for controlling the cancellation cleanup service",
    )
    event_persister: ServerServicesEventPersisterSettings = Field(
        default_factory=ServerServicesEventPersisterSettings,
        description="Settings for controlling the event persister service",
    )
    event_logger: ServerServicesEventLoggerSettings = Field(
        default_factory=ServerServicesEventLoggerSettings,
        description="Settings for controlling the event logger service",
    )
    foreman: ServerServicesForemanSettings = Field(
        default_factory=ServerServicesForemanSettings,
        description="Settings for controlling the foreman service",
    )
    late_runs: ServerServicesLateRunsSettings = Field(
        default_factory=ServerServicesLateRunsSettings,
        description="Settings for controlling the late runs service",
    )
    scheduler: ServerServicesSchedulerSettings = Field(
        default_factory=ServerServicesSchedulerSettings,
        description="Settings for controlling the scheduler service",
    )
    pause_expirations: ServerServicesPauseExpirationsSettings = Field(
        default_factory=ServerServicesPauseExpirationsSettings,
        description="Settings for controlling the pause expiration service",
    )
    repossessor: ServerServicesRepossessorSettings = Field(
        default_factory=ServerServicesRepossessorSettings,
        description="Settings for controlling the repossessor service",
    )
    task_run_recorder: ServerServicesTaskRunRecorderSettings = Field(
        default_factory=ServerServicesTaskRunRecorderSettings,
        description="Settings for controlling the task run recorder service",
    )
    triggers: ServerServicesTriggersSettings = Field(
        default_factory=ServerServicesTriggersSettings,
        description="Settings for controlling the triggers service",
    )
