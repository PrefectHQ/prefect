from pydantic import AliasChoices, AliasPath, Field

from prefect.settings.base import (
    PrefectBaseSettings,
    _build_settings_config,
)
from prefect.types import ClientRetryExtraCodes


class ClientMetricsSettings(PrefectBaseSettings):
    """
    Settings for controlling metrics reporting from the client
    """

    model_config = _build_settings_config(("client", "metrics"))

    enabled: bool = Field(
        default=False,
        description="Whether or not to enable Prometheus metrics in the client.",
        # Using alias for backwards compatibility. Need to duplicate the prefix because
        # Pydantic does not allow the alias to be prefixed with the env_prefix. The AliasPath
        # needs to be first to ensure that init kwargs take precedence over env vars.
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_client_metrics_enabled",
            "prefect_client_enable_metrics",
        ),
    )

    port: int = Field(
        default=4201, description="The port to expose the client Prometheus metrics on."
    )


class ClientSettings(PrefectBaseSettings):
    """
    Settings for controlling API client behavior
    """

    model_config = _build_settings_config(("client",))

    max_retries: int = Field(
        default=5,
        ge=0,
        description="""
        The maximum number of retries to perform on failed HTTP requests.
        Defaults to 5. Set to 0 to disable retries.
        See `PREFECT_CLIENT_RETRY_EXTRA_CODES` for details on which HTTP status codes are
        retried.
        """,
    )

    retry_jitter_factor: float = Field(
        default=0.2,
        ge=0.0,
        description="""
        A value greater than or equal to zero to control the amount of jitter added to retried
        client requests. Higher values introduce larger amounts of jitter.
        Set to 0 to disable jitter. See `clamped_poisson_interval` for details on the how jitter
        can affect retry lengths.
        """,
    )

    retry_extra_codes: ClientRetryExtraCodes = Field(
        default_factory=set,
        description="""
        A list of extra HTTP status codes to retry on. Defaults to an empty list.
        429, 502 and 503 are always retried. Please note that not all routes are idempotent and retrying
        may result in unexpected behavior.
        """,
        examples=["404,429,503", "429", {404, 429, 503}],
    )

    csrf_support_enabled: bool = Field(
        default=True,
        description="""
        Determines if CSRF token handling is active in the Prefect client for API
        requests.

        When enabled (`True`), the client automatically manages CSRF tokens by
        retrieving, storing, and including them in applicable state-changing requests
        """,
    )

    metrics: ClientMetricsSettings = Field(
        default_factory=ClientMetricsSettings,
        description="Settings for controlling metrics reporting from the client",
    )
