from pydantic import AliasChoices, AliasPath, Field

from prefect.settings.base import (
    COMMON_CONFIG_DICT,
    PrefectBaseSettings,
    PrefectSettingsConfigDict,
)


class ServerDeploymentsSettings(PrefectBaseSettings):
    model_config = PrefectSettingsConfigDict(
        **COMMON_CONFIG_DICT,
        env_prefix="PREFECT_SERVER_DEPLOYMENTS_",
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
