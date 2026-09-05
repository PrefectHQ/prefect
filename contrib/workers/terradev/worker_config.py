"""Configuration schema for the Terradev work pool worker."""

from typing import Optional

import pydantic

from prefect.workers.base import BaseJobConfiguration


class TerradevWorkerConfiguration(BaseJobConfiguration):
    """Work pool configuration for Terradev GPU provisioning."""

    provider: Optional[str] = pydantic.Field(
        default=None,
        description=(
            "GPU provider to use. If omitted, Terradev selects the cheapest "
            "available provider. One of: runpod, vastai, tensordock, crusoe, "
            "hyperstack, latitude, e2enetworks, gcore, aws, gcp, azure, "
            "digitalocean, inferx, baseten, siliconflow, huggingface, yottalabs."
        ),
    )
    gpu_type: str = pydantic.Field(
        default="A100",
        description="GPU model to request (H100, A100, RTX4090, L40S, ...).",
    )
    region: Optional[str] = pydantic.Field(
        default=None,
        description="Preferred provider region. Falls back to cheapest if unavailable.",
    )
    max_price_per_hour: Optional[float] = pydantic.Field(
        default=None,
        description="Maximum acceptable hourly cost in USD. Skips providers above this.",
    )
    spot: bool = pydantic.Field(
        default=False,
        description="Allow spot/interruptible instances for lower cost.",
    )
    ssh_user: str = pydantic.Field(
        default="ubuntu",
        description="SSH user on the provisioned instance.",
    )
