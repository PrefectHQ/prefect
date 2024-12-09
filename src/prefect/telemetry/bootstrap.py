from typing import TYPE_CHECKING, Union

import prefect.settings
from prefect.client.base import ServerType, determine_server_type

if TYPE_CHECKING:
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.trace import TracerProvider


def setup_telemetry() -> (
    Union[
        tuple["TracerProvider", "MeterProvider", "LoggerProvider"],
        tuple[None, None, None],
    ]
):
    settings = prefect.settings.get_current_settings()
    if not settings.experiments.telemetry_enabled:
        return None, None, None

    server_type = determine_server_type()
    if server_type != ServerType.CLOUD:
        return None, None, None

    if not settings.api.key:
        raise ValueError(
            "A Prefect Cloud API key is required to enable telemetry. Please set "
            "the `PREFECT_API_KEY` environment variable or authenticate with "
            "Prefect Cloud via the `prefect cloud login` command."
        )

    assert settings.api.url

    # This import is here to defer importing of the `opentelemetry` packages.
    try:
        from .instrumentation import setup_exporters
    except ImportError as exc:
        raise ValueError(
            "Unable to import OpenTelemetry instrumentation libraries. Please "
            "ensure you have installed the `otel` extra when installing Prefect: "
            "`pip install 'prefect[otel]'`"
        ) from exc

    return setup_exporters(settings.api.url, settings.api.key.get_secret_value())
