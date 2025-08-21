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


class EcsSettings(PrefectBaseSettings):
    model_config = build_settings_config(("integrations", "aws", "ecs"))

    observer: EcsObserverSettings = Field(
        description="Settings for controlling ECS observer behavior.",
        default_factory=EcsObserverSettings,
    )


class AwsSettings(PrefectBaseSettings):
    model_config = build_settings_config(("integrations", "aws"))

    ecs: EcsSettings = Field(
        description="Settings for controlling ECS behavior.",
        default_factory=EcsSettings,
    )
