from datetime import timedelta
from typing import ClassVar

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class ServerTasksSchedulingSettings(PrefectBaseSettings):
    """
    Settings for controlling server-side behavior related to task scheduling
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "tasks", "scheduling")
    )

    max_scheduled_queue_size: int = Field(
        default=1000,
        description="The maximum number of scheduled tasks to queue for submission.",
        validation_alias=AliasChoices(
            AliasPath("max_scheduled_queue_size"),
            "prefect_server_tasks_scheduling_max_scheduled_queue_size",
            "prefect_task_scheduling_max_scheduled_queue_size",
        ),
    )

    max_retry_queue_size: int = Field(
        default=1000,
        description="The maximum number of retries to queue for submission.",
        validation_alias=AliasChoices(
            AliasPath("max_retry_queue_size"),
            "prefect_server_tasks_scheduling_max_retry_queue_size",
            "prefect_task_scheduling_max_retry_queue_size",
        ),
    )

    pending_task_timeout: timedelta = Field(
        default=timedelta(0),
        description="How long before a PENDING task is made available to another task worker.",
        validation_alias=AliasChoices(
            AliasPath("pending_task_timeout"),
            "prefect_server_tasks_scheduling_pending_task_timeout",
            "prefect_task_scheduling_pending_task_timeout",
        ),
    )

    inflight_visibility_timeout: int = Field(
        default=30,
        description=(
            "Seconds before an in-flight task run is considered stale and "
            "re-enqueued. Only used by backends that track in-flight state "
            "(e.g., the Redis backend)."
        ),
        validation_alias=AliasChoices(
            AliasPath("inflight_visibility_timeout"),
            "prefect_server_tasks_scheduling_inflight_visibility_timeout",
            "prefect_task_scheduling_inflight_visibility_timeout",
        ),
    )

    stream_consumer_cleanup_interval: int = Field(
        default=60,
        description="Seconds between stale consumer cleanup passes. Only used by the Redis Streams backend.",
        validation_alias=AliasChoices(
            AliasPath("stream_consumer_cleanup_interval"),
            "prefect_server_tasks_scheduling_stream_consumer_cleanup_interval",
            "prefect_task_scheduling_stream_consumer_cleanup_interval",
        ),
    )

    stream_consumer_idle_threshold: int = Field(
        default=300,
        description="Seconds before an idle consumer is considered stale and removed. Only used by the Redis Streams backend.",
        validation_alias=AliasChoices(
            AliasPath("stream_consumer_idle_threshold"),
            "prefect_server_tasks_scheduling_stream_consumer_idle_threshold",
            "prefect_task_scheduling_stream_consumer_idle_threshold",
        ),
    )

    stream_max_retries: int = Field(
        default=3,
        description="Max redelivery attempts before a task is moved to the dead letter queue. Only used by the Redis Streams backend.",
        validation_alias=AliasChoices(
            AliasPath("stream_max_retries"),
            "prefect_server_tasks_scheduling_stream_max_retries",
            "prefect_task_scheduling_stream_max_retries",
        ),
    )

    dequeue_block_ms: int = Field(
        default=1000,
        gt=0,
        description=(
            "Milliseconds to block on each XREADGROUP call per task key. "
            "Lower values release Redis connections faster at the cost of "
            "more frequent round-trips in the idle case. Only used by the "
            "Redis Streams backend."
        ),
    )

    backend: str = Field(
        default="prefect.server.task_queue.memory",
        description=(
            "Module path for the task queue backend. The module must export "
            "a TaskQueueBackend class that conforms to the protocol in "
            "prefect.server.task_queue. Use 'prefect_redis.task_queue' "
            "for Redis-backed distributed queue across server replicas."
        ),
        validation_alias=AliasChoices(
            AliasPath("backend"),
            "prefect_server_tasks_scheduling_backend",
            "prefect_task_scheduling_backend",
        ),
    )


class ServerTasksSettings(PrefectBaseSettings):
    """
    Settings for controlling server-side behavior related to tasks
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "tasks")
    )

    tag_concurrency_slot_wait_seconds: float = Field(
        default=10,
        ge=0,
        description="The number of seconds to wait before retrying when a task run cannot secure a concurrency slot from the server.",
        validation_alias=AliasChoices(
            AliasPath("tag_concurrency_slot_wait_seconds"),
            "prefect_server_tasks_tag_concurrency_slot_wait_seconds",
            "prefect_task_run_tag_concurrency_slot_wait_seconds",
        ),
    )

    max_cache_key_length: int = Field(
        default=2000,
        description="The maximum number of characters allowed for a task run cache key.",
        validation_alias=AliasChoices(
            AliasPath("max_cache_key_length"),
            "prefect_server_tasks_max_cache_key_length",
            "prefect_api_task_cache_key_max_length",
        ),
    )

    scheduling: ServerTasksSchedulingSettings = Field(
        default_factory=ServerTasksSchedulingSettings,
        description="Settings for controlling server-side behavior related to task scheduling",
    )
