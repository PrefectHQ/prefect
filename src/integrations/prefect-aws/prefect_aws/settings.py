from __future__ import annotations

from typing import Optional

from pydantic import Field

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class EcsObserverSqsSettings(PrefectBaseSettings):
    model_config = build_settings_config(
        ("integrations", "aws", "ecs", "observer", "sqs")
    )

    queue_name: str = Field(
        default="prefect-ecs-tasks-events",
        description="The name of the SQS queue to watch for Prefect-submitted ECS tasks.",
    )

    queue_region: Optional[str] = Field(
        default=None,
        description="The region of the SQS queue to watch for Prefect-submitted ECS tasks.",
    )


class EcsObserverSettings(PrefectBaseSettings):
    model_config = build_settings_config(("integrations", "aws", "ecs", "observer"))

    enabled: bool = Field(
        default=True,
        description="Whether to enable the ECS observer.",
    )

    sqs: EcsObserverSqsSettings = Field(
        description="Settings for controlling ECS observer SQS behavior.",
        default_factory=EcsObserverSqsSettings,
    )


class EcsWorkerSettings(PrefectBaseSettings):
    """Settings for controlling ECS worker behavior."""

    model_config = build_settings_config(("integrations", "aws", "ecs", "worker"))

    create_task_run_max_attempts: int = Field(
        default=3,
        description=(
            "The maximum number of attempts to create an ECS task run. "
            "Increase this value to allow more retries when task creation fails "
            "due to transient issues like resource constraints during cluster "
            "scaling."
        ),
        ge=1,
    )

    create_task_run_min_delay_seconds: int = Field(
        default=1,
        description=(
            "The minimum fixed delay in seconds between retries when creating "
            "an ECS task run."
        ),
        ge=0,
    )

    create_task_run_min_delay_jitter_seconds: int = Field(
        default=0,
        description=(
            "The minimum jitter in seconds to add to the delay between retries "
            "when creating an ECS task run."
        ),
        ge=0,
    )

    create_task_run_max_delay_jitter_seconds: int = Field(
        default=3,
        description=(
            "The maximum jitter in seconds to add to the delay between retries "
            "when creating an ECS task run."
        ),
        ge=0,
    )


class EcsSettings(PrefectBaseSettings):
    model_config = build_settings_config(("integrations", "aws", "ecs"))

    observer: EcsObserverSettings = Field(
        description="Settings for controlling ECS observer behavior.",
        default_factory=EcsObserverSettings,
    )

    worker: EcsWorkerSettings = Field(
        description="Settings for controlling ECS worker behavior.",
        default_factory=EcsWorkerSettings,
    )


class RdsIAMSettings(PrefectBaseSettings):
    """Settings for controlling RDS IAM authentication."""

    model_config = build_settings_config(("integrations", "aws", "rds", "iam"))

    enabled: bool = Field(
        default=False,
        description="Controls whether to use IAM authentication for RDS PostgreSQL connections.",
    )

    region_name: Optional[str] = Field(
        default=None,
        description="The AWS region for IAM authentication. If not provided, it will be inferred from the environment.",
    )


class RdsSettings(PrefectBaseSettings):
    """Settings for AWS RDS integration."""

    model_config = build_settings_config(("integrations", "aws", "rds"))

    iam: RdsIAMSettings = Field(
        description="Settings for controlling RDS IAM authentication.",
        default_factory=RdsIAMSettings,
    )


class AwsSettings(PrefectBaseSettings):
    model_config = build_settings_config(("integrations", "aws"))

    ecs: EcsSettings = Field(
        description="Settings for controlling ECS behavior.",
        default_factory=EcsSettings,
    )

    rds: RdsSettings = Field(
        description="Settings for controlling RDS behavior.",
        default_factory=RdsSettings,
    )
