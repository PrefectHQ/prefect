from __future__ import annotations

from pydantic import Field

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class CloudRunV2WorkerSettings(PrefectBaseSettings):
    """Settings for controlling Cloud Run V2 worker behavior."""

    model_config = build_settings_config(
        ("integrations", "gcp", "cloud_run_v2", "worker")
    )

    create_job_max_attempts: int = Field(
        default=3,
        ge=1,
        description=(
            "The maximum number of attempts to create a Cloud Run V2 job. "
            "Increase this value to allow more retries when job creation fails "
            "due to transient issues like HTTP 429/500/503 from the Cloud Run API."
        ),
    )

    create_job_initial_delay_seconds: float = Field(
        default=1.0,
        gt=0,
        description=(
            "The initial delay in seconds for exponential jitter backoff between "
            "retries when creating a Cloud Run V2 job."
        ),
    )

    create_job_max_delay_seconds: float = Field(
        default=10.0,
        gt=0,
        description=(
            "The maximum delay in seconds for exponential jitter backoff between "
            "retries when creating a Cloud Run V2 job."
        ),
    )


class CloudRunV2Settings(PrefectBaseSettings):
    """Settings for the Cloud Run V2 integration."""

    model_config = build_settings_config(("integrations", "gcp", "cloud_run_v2"))

    worker: CloudRunV2WorkerSettings = Field(
        description="Settings for controlling Cloud Run V2 worker behavior.",
        default_factory=CloudRunV2WorkerSettings,
    )


class GcpSettings(PrefectBaseSettings):
    """Settings for the prefect-gcp integration."""

    model_config = build_settings_config(("integrations", "gcp"))

    cloud_run_v2: CloudRunV2Settings = Field(
        description="Settings for controlling Cloud Run V2 behavior.",
        default_factory=CloudRunV2Settings,
    )
