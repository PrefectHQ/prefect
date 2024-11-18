from datetime import timedelta

from pydantic import AliasChoices, AliasPath, Field

from prefect.settings.base import PrefectBaseSettings, _build_settings_config


class ServerServicesCancellationCleanupSettings(PrefectBaseSettings):
    """
    Settings for controlling the cancellation cleanup service
    """

    model_config = _build_settings_config(
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


class ServerServicesEventPersisterSettings(PrefectBaseSettings):
    """
    Settings for controlling the event persister service
    """

    model_config = _build_settings_config(("server", "services", "event_persister"))

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


class ServerServicesFlowRunNotificationsSettings(PrefectBaseSettings):
    """
    Settings for controlling the flow run notifications service
    """

    model_config = _build_settings_config(
        ("server", "services", "flow_run_notifications")
    )

    enabled: bool = Field(
        default=True,
        description="Whether or not to start the flow run notifications service in the server application.",
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_server_services_flow_run_notifications_enabled",
            "prefect_api_services_flow_run_notifications_enabled",
        ),
    )


class ServerServicesForemanSettings(PrefectBaseSettings):
    """
    Settings for controlling the foreman service
    """

    model_config = _build_settings_config(("server", "services", "foreman"))

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


class ServerServicesLateRunsSettings(PrefectBaseSettings):
    """
    Settings for controlling the late runs service
    """

    model_config = _build_settings_config(("server", "services", "late_runs"))

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


class ServerServicesSchedulerSettings(PrefectBaseSettings):
    """
    Settings for controlling the scheduler service
    """

    model_config = _build_settings_config(("server", "services", "scheduler"))

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


class ServerServicesPauseExpirationsSettings(PrefectBaseSettings):
    """
    Settings for controlling the pause expiration service
    """

    model_config = _build_settings_config(("server", "services", "pause_expirations"))

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


class ServerServicesTaskRunRecorderSettings(PrefectBaseSettings):
    """
    Settings for controlling the task run recorder service
    """

    model_config = _build_settings_config(("server", "services", "task_run_recorder"))

    enabled: bool = Field(
        default=True,
        description="Whether or not to start the task run recorder service in the server application.",
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_server_services_task_run_recorder_enabled",
            "prefect_api_services_task_run_recorder_enabled",
        ),
    )


class ServerServicesTriggersSettings(PrefectBaseSettings):
    """
    Settings for controlling the triggers service
    """

    model_config = _build_settings_config(("server", "services", "triggers"))

    enabled: bool = Field(
        default=True,
        description="Whether or not to start the triggers service in the server application.",
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_server_services_triggers_enabled",
            "prefect_api_services_triggers_enabled",
        ),
    )


class ServerServicesSettings(PrefectBaseSettings):
    """
    Settings for controlling server services
    """

    model_config = _build_settings_config(("server", "services"))

    cancellation_cleanup: ServerServicesCancellationCleanupSettings = Field(
        default_factory=ServerServicesCancellationCleanupSettings,
        description="Settings for controlling the cancellation cleanup service",
    )
    event_persister: ServerServicesEventPersisterSettings = Field(
        default_factory=ServerServicesEventPersisterSettings,
        description="Settings for controlling the event persister service",
    )
    flow_run_notifications: ServerServicesFlowRunNotificationsSettings = Field(
        default_factory=ServerServicesFlowRunNotificationsSettings,
        description="Settings for controlling the flow run notifications service",
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
    task_run_recorder: ServerServicesTaskRunRecorderSettings = Field(
        default_factory=ServerServicesTaskRunRecorderSettings,
        description="Settings for controlling the task run recorder service",
    )
    triggers: ServerServicesTriggersSettings = Field(
        default_factory=ServerServicesTriggersSettings,
        description="Settings for controlling the triggers service",
    )
