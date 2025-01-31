from typing import TYPE_CHECKING, Union

import prefect.settings
from prefect.client.base import ServerType, determine_server_type
from prefect.logging.loggers import get_logger

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)

if TYPE_CHECKING:
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.trace import TracerProvider


def setup_telemetry() -> Union[
    tuple["TracerProvider", "MeterProvider", "LoggerProvider"],
    tuple[None, None, None],
]:
    settings = prefect.settings.get_current_settings()

    server_type = determine_server_type()
    if server_type != ServerType.CLOUD:
        return None, None, None

    if not settings.cloud.enable_orchestration_telemetry:
        return None, None, None

    if not settings.api.key:
        logger.warning(
            "A Prefect Cloud API key is required to enable telemetry. Please set "
            "the `PREFECT_API_KEY` environment variable or authenticate with "
            "Prefect Cloud via the `prefect cloud login` command."
        )
        return None, None, None

    assert settings.api.url

    # This import is here to defer importing of the `opentelemetry` packages.
    try:
        from .instrumentation import setup_exporters
    except ImportError:
        return None, None, None

    return setup_exporters(settings.api.url, settings.api.key.get_secret_value())
