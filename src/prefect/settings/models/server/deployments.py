from pydantic import AliasChoices, AliasPath, Field

from prefect.settings.base import PrefectBaseSettings, PrefectSettingsConfigDict


class ServerDeploymentsSettings(PrefectBaseSettings):
    model_config = PrefectSettingsConfigDict(
        env_prefix="PREFECT_SERVER_DEPLOYMENTS_",
        env_file=".env",
        extra="ignore",
        toml_file="prefect.toml",
        prefect_toml_table_header=("server", "deployments"),
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
