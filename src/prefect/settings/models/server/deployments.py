from pydantic import AliasChoices, AliasPath, Field

from prefect.settings.base import PrefectBaseSettings, _build_settings_config


class ServerDeploymentsSettings(PrefectBaseSettings):
    model_config = _build_settings_config(("server", "deployments"))

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
