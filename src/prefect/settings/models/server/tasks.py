from datetime import timedelta

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings


class ServerTasksSchedulingSettings(PrefectBaseSettings):
    """
    Settings for controlling server-side behavior related to task scheduling
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PREFECT_SERVER_TASKS_SCHEDULING_",
        extra="ignore",
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
        default=100,
        description="The maximum number of retries to queue for submission.",
        validation_alias=AliasChoices(
            AliasPath("max_retry_queue_size"),
            "prefect_server_tasks_scheduling_max_retry_queue_size",
            "prefect_task_scheduling_max_retry_queue_size",
        ),
    )

    pending_task_timeout: timedelta = Field(
        default=timedelta(0),
        description="How long before a PENDING task are made available to another task worker.",
        validation_alias=AliasChoices(
            AliasPath("pending_task_timeout"),
            "prefect_server_tasks_scheduling_pending_task_timeout",
            "prefect_task_scheduling_pending_task_timeout",
        ),
    )


class ServerTasksSettings(PrefectBaseSettings):
    """
    Settings for controlling server-side behavior related to tasks
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PREFECT_SERVER_TASKS_",
        extra="ignore",
    )

    tag_concurrency_slot_wait_seconds: float = Field(
        default=30,
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
