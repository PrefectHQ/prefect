from typing import ClassVar, Optional

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config
from prefect.types import TaskRetryDelaySeconds


class TasksRunnerSettings(PrefectBaseSettings):
    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("tasks", "runner")
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

    process_pool_max_workers: Optional[int] = Field(
        default=None,
        gt=0,
        description="The maximum number of workers for ProcessPoolTaskRunner.",
    )


class TasksSchedulingSettings(PrefectBaseSettings):
    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("tasks", "scheduling")
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
    model_config: ClassVar[SettingsConfigDict] = build_settings_config(("tasks",))

    refresh_cache: bool = Field(
        default=False,
        description="If `True`, enables a refresh of cached results: re-executing the task will refresh the cached results.",
    )

    default_no_cache: bool = Field(
        default=False,
        description="If `True`, sets the default cache policy on all tasks to `NO_CACHE`.",
    )

    disable_caching: bool = Field(
        default=False,
        description="If `True`, disables caching on all tasks regardless of cache policy.",
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

    default_retry_delay_seconds: TaskRetryDelaySeconds = Field(
        default=0,
        description="This value sets the default retry delay seconds for all tasks.",
        validation_alias=AliasChoices(
            AliasPath("default_retry_delay_seconds"),
            "prefect_tasks_default_retry_delay_seconds",
            "prefect_task_default_retry_delay_seconds",
        ),
    )

    default_persist_result: Optional[bool] = Field(
        default=None,
        description="If `True`, results will be persisted by default for all tasks. Set to `False` to disable persistence by default. "
        "Note that setting to `False` will override the behavior set by a parent flow or task.",
    )

    runner: TasksRunnerSettings = Field(
        default_factory=TasksRunnerSettings,
        description="Settings for controlling task runner behavior",
    )

    scheduling: TasksSchedulingSettings = Field(
        default_factory=TasksSchedulingSettings,
        description="Settings for controlling client-side task scheduling behavior",
    )
