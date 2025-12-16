from typing import ClassVar

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class ServerDeploymentsSettings(PrefectBaseSettings):
    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "deployments")
    )

    concurrency_slot_wait_seconds: float = Field(
        default=5.0,
        ge=0.0,
        description=(
            "The number of seconds to wait before retrying when a deployment flow run"
            " cannot secure a concurrency slot from the server. This value should be less"
            " than the worker's prefetch_seconds setting (default 10s) to ensure runs in"
            " AwaitingConcurrencySlot state become visible to workers within their polling"
            " window."
        ),
        validation_alias=AliasChoices(
            AliasPath("concurrency_slot_wait_seconds"),
            "prefect_server_deployments_concurrency_slot_wait_seconds",
            "prefect_deployment_concurrency_slot_wait_seconds",
        ),
    )
