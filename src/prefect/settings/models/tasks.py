from typing import Optional, Union

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings


class TasksRunnerSettings(PrefectBaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PREFECT_TASKS_RUNNER_", env_file=".env", extra="ignore"
    )

    thread_pool_max_workers: Optional[int] = Field(
        default=None,
        gt=0,
        description="The maximum number of workers for ThreadPoolTaskRunner.",
        validation_alias=AliasChoices(
            AliasPath("thread_pool_max_workers"),
            "prefect_tasks_runner_thread_pool_max_workers",
            "prefect_task_runner_thread_pool_max_workers",
        ),
    )


class TasksSchedulingSettings(PrefectBaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PREFECT_TASKS_SCHEDULING_", env_file=".env", extra="ignore"
    )

    default_storage_block: Optional[str] = Field(
        default=None,
        description="The `block-type/block-document` slug of a block to use as the default storage for autonomous tasks.",
        validation_alias=AliasChoices(
            AliasPath("default_storage_block"),
            "prefect_tasks_scheduling_default_storage_block",
            "prefect_task_scheduling_default_storage_block",
        ),
    )

    delete_failed_submissions: bool = Field(
        default=True,
        description="Whether or not to delete failed task submissions from the database.",
        validation_alias=AliasChoices(
            AliasPath("delete_failed_submissions"),
            "prefect_tasks_scheduling_delete_failed_submissions",
            "prefect_task_scheduling_delete_failed_submissions",
        ),
    )


class TasksSettings(PrefectBaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PREFECT_TASKS_", env_file=".env", extra="ignore"
    )

    refresh_cache: bool = Field(
        default=False,
        description="If `True`, enables a refresh of cached results: re-executing the task will refresh the cached results.",
    )

    default_retries: int = Field(
        default=0,
        ge=0,
        description="This value sets the default number of retries for all tasks.",
        validation_alias=AliasChoices(
            AliasPath("default_retries"),
            "prefect_tasks_default_retries",
            "prefect_task_default_retries",
        ),
    )

    default_retry_delay_seconds: Union[int, float, list[float]] = Field(
        default=0,
        description="This value sets the default retry delay seconds for all tasks.",
        validation_alias=AliasChoices(
            AliasPath("default_retry_delay_seconds"),
            "prefect_tasks_default_retry_delay_seconds",
            "prefect_task_default_retry_delay_seconds",
        ),
    )

    runner: TasksRunnerSettings = Field(
        default_factory=TasksRunnerSettings,
        description="Settings for controlling task runner behavior",
    )

    scheduling: TasksSchedulingSettings = Field(
        default_factory=TasksSchedulingSettings,
        description="Settings for controlling client-side task scheduling behavior",
    )
