from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings


class ServerDeploymentsSettings(PrefectBaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PREFECT_SERVER_DEPLOYMENTS_", env_file=".env", extra="ignore"
    )

    concurrency_slot_wait_seconds: float = Field(
        default=30.0,
        ge=0.0,
        description=(
            "The number of seconds to wait before retrying when a deployment flow run"
            " cannot secure a concurrency slot from the server."
        ),
        validation_alias=AliasChoices(
            AliasPath("concurrency_slot_wait_seconds"),
            "prefect_server_deployments_concurrency_slot_wait_seconds",
            "prefect_deployment_concurrency_slot_wait_seconds",
        ),
    )
