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

    pending_task_timeout: timedelta = Field(
        default=timedelta(0),
        description="How long before a PENDING task are made available to another task worker.",
        validation_alias=AliasChoices(
            AliasPath("pending_task_timeout"),
            "prefect_server_tasks_scheduling_pending_task_timeout",
            "prefect_task_scheduling_pending_task_timeout",
        ),
    )

    delivery_visibility_timeout: timedelta = Field(
        default=timedelta(seconds=30),
        gt=timedelta(0),
        description=(
            "How long a deferred task delivery may remain unacknowledged before "
            "another TaskWorker can claim it."
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
