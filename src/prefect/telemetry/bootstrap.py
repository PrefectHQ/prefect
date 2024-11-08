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

    assert settings.api.key
    assert settings.api.url

    # This import is here to defer importing of the `opentelemetry` packages.
    from .instrumentation import setup_exporters

    return setup_exporters(settings.api.url, settings.api.key.get_secret_value())
