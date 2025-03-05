from typing import Optional

from pydantic import AliasChoices, AliasPath, Field

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class KubernetesWorkerSettings(PrefectBaseSettings):
    model_config = build_settings_config(("integrations", "kubernetes", "worker"))

    api_key_secret_name: Optional[str] = Field(
        default=None,
        description="The name of the secret the worker's API key is stored in.",
    )

    api_key_secret_key: Optional[str] = Field(
        default=None,
        description="The key of the secret the worker's API key is stored in.",
    )

    create_secret_for_api_key: bool = Field(
        default=False,
        description="If `True`, the worker will create a secret in the same namespace as created Kubernetes jobs to store the Prefect API key.",
        validation_alias=AliasChoices(
            AliasPath("create_secret_for_api_key"),
            "prefect_integrations_kubernetes_worker_create_secret_for_api_key",
            "prefect_kubernetes_worker_store_prefect_api_in_secret",
        ),
    )

    add_tcp_keepalive: bool = Field(
        default=True,
        description="If `True`, the worker will add TCP keepalive to the Kubernetes client.",
        validation_alias=AliasChoices(
            AliasPath("add_tcp_keepalive"),
            "prefect_integrations_kubernetes_worker_add_tcp_keepalive",
            "prefect_kubernetes_worker_add_tcp_keepalive",
        ),
    )


class KubernetesSettings(PrefectBaseSettings):
    model_config = build_settings_config(("integrations", "kubernetes"))

    cluster_uid: Optional[str] = Field(
        default=None,
        description="A unique identifier for the current cluster being used.",
        validation_alias=AliasChoices(
            AliasPath("cluster_uid"),
            "prefect_integrations_kubernetes_cluster_uid",
            "prefect_kubernetes_cluster_uid",
        ),
    )

    worker: KubernetesWorkerSettings = Field(
        description="Settings for controlling Kubernetes worker behavior.",
        default_factory=KubernetesWorkerSettings,
    )
