"""
internal module for configuring observability tooling (logfire, etc.)
"""

from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogfireSettings(BaseSettings):
    """
    configuration for logfire observability integration.
    """

    model_config = SettingsConfigDict(
        env_prefix="PREFECT_LOGFIRE_",
        extra="ignore",
    )

    enabled: bool = Field(
        default=False,
        description="whether to enable logfire observability",
    )

    write_token: str | None = Field(
        default=None,
        description="API token for writing to logfire. required when enabled=true.",
    )

    sampling_head_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="fraction of traces to sample upfront (0.0-1.0). reduces total volume.",
    )

    sampling_level_threshold: str = Field(
        default="warn",
        description="minimum log level to always include (debug, info, warn, error). keeps all warnings/errors.",
    )

    sampling_duration_threshold: float = Field(
        default=5.0,
        ge=0.0,
        description="minimum duration in seconds to always include. catches slow operations.",
    )

    sampling_background_rate: float = Field(
        default=0.01,
        ge=0.0,
        le=1.0,
        description="fraction of non-notable traces to keep anyway (0.0-1.0). maintains baseline visibility.",
    )


def configure_logfire() -> Any | None:
    """
    configure and return logfire instance with sampling, or None if disabled.

    this function:
    1. checks if logfire is enabled via PREFECT_LOGFIRE_ENABLED
    2. validates PREFECT_LOGFIRE_WRITE_TOKEN is set
    3. loads sampling configuration from env vars
    4. configures logfire with sampling options
    5. returns configured logfire module (or None if disabled)

    can be called multiple times safely - logfire.configure is idempotent.
    """
    # load logfire settings from env vars
    settings = LogfireSettings()

    if not settings.enabled:
        return None

    if settings.write_token is None:
        raise ValueError(
            "PREFECT_LOGFIRE_WRITE_TOKEN must be set when PREFECT_LOGFIRE_ENABLED is true"
        )

    try:
        import logfire  # pyright: ignore
    except ImportError as exc:
        raise ImportError(
            "logfire is not installed. install it with: uv add logfire"
        ) from exc

    # build sampling options
    sampling_options = logfire.SamplingOptions.level_or_duration(
        head=settings.sampling_head_rate,
        level_threshold=settings.sampling_level_threshold,
        duration_threshold=settings.sampling_duration_threshold,
        background_rate=settings.sampling_background_rate,
    )

    logfire.configure(token=settings.write_token, sampling=sampling_options)  # pyright: ignore
    return logfire
