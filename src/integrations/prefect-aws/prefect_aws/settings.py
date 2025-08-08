from __future__ import annotations

from functools import partial
from typing import Annotated, Optional, Union

from pydantic import BeforeValidator, Field

from prefect.settings.base import PrefectBaseSettings, build_settings_config
from prefect.types import validate_set_T_from_delim_string


def _validate_label_filters(value: dict[str, str] | str | None) -> dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    split_value = value.split(",")
    return {
        k.strip(): v.strip() for k, v in (item.split("=", 1) for item in split_value)
    }


LabelFilters = Annotated[
    Union[dict[str, str], str, None], BeforeValidator(_validate_label_filters)
]
Namespaces = Annotated[
    Union[set[str], str, None],
    BeforeValidator(partial(validate_set_T_from_delim_string, type_=str)),
]


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
