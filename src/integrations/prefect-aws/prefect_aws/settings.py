from typing import Optional

from pydantic import Field

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class AwsEcsWorkerSettings(PrefectBaseSettings):
    model_config = build_settings_config(("integrations", "aws", "ecs_worker"))

    api_secret_arn: Optional[str] = Field(
        default=None,
        description="The ARN of the secret to use for the ECS worker API key.",
        examples=[
            "arn:aws:secretsmanager:us-east-1:123456789012:secret:prefect-worker-api-key"
        ],
    )


class AwsSettings(PrefectBaseSettings):
    model_config = build_settings_config(("integrations", "aws"))

    ecs_worker: AwsEcsWorkerSettings = Field(
        default_factory=AwsEcsWorkerSettings,
        description="Settings for the ECS worker.",
    )
