import logging
import os
import re
from typing import Optional
from uuid import UUID

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

import prefect.settings
from prefect.client.base import ServerType, determine_server_type

from .processors import InFlightSpanProcessor

UUID_REGEX = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

ACCOUNTS_PREFIX = "accounts/"
ACCOUNT_ID_REGEX = f"{ACCOUNTS_PREFIX}{UUID_REGEX}"

WORKSPACES_PREFIX = "workspaces/"
WORKSPACE_ID_REGEX = f"{WORKSPACES_PREFIX}{UUID_REGEX}"


def extract_account_and_workspace_id(url) -> tuple[UUID, UUID]:
    account_id, workspace_id = None, None

    if res := re.search(ACCOUNT_ID_REGEX, url):
        account_id = UUID(res.group().removeprefix(ACCOUNTS_PREFIX))

    if res := re.search(WORKSPACE_ID_REGEX, url):
        workspace_id = UUID(res.group().removeprefix(WORKSPACES_PREFIX))

    if account_id and workspace_id:
        return account_id, workspace_id

    raise ValueError("Could not extract account and workspace id from url")


_log_handler: Optional[LoggingHandler] = None


def setup_prefect_telemetry() -> None:
    """Configure OpenTelemetry exporters for Prefect telemetry."""
    settings = prefect.settings.get_current_settings()
    if not settings.experiments.telemetry_enabled:
        return

    server_type = determine_server_type()
    if server_type != ServerType.CLOUD:
        return

    assert settings.api.key

    api_key = settings.api.key.get_secret_value()
    account_id, workspace_id = extract_account_and_workspace_id(settings.cloud.api_url)
    telemetry_url = settings.cloud.api_url + "/telemetry/"

    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    resource = Resource.create(
        {
            "service.name": "prefect",
            "service.instance.id": os.uname().nodename,
            "prefect.account": str(account_id),
            "prefect.workspace": str(workspace_id),
        }
    )

    _setup_trace_provider(resource, headers, telemetry_url)
    _setup_metric_provider(resource, headers, telemetry_url)
    _setup_logger_provider(resource, headers, telemetry_url)


def _setup_trace_provider(
    resource: Resource, headers: dict[str, str], telemetry_url: str
) -> None:
    trace_provider = TracerProvider(resource=resource)
    otlp_span_exporter = OTLPSpanExporter(
        endpoint=f"{telemetry_url}/v1/traces",
        headers=headers,
    )
    trace_provider.add_span_processor(InFlightSpanProcessor(otlp_span_exporter))
    trace.set_tracer_provider(trace_provider)


def _setup_metric_provider(
    resource: Resource, headers: dict[str, str], telemetry_url: str
) -> None:
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=f"{telemetry_url}/v1/metrics",
            headers=headers,
        )
    )
    metric_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(metric_provider)


def _setup_logger_provider(
    resource: Resource, headers: dict[str, str], telemetry_url: str
) -> None:
    global _log_handler
    logger_provider = LoggerProvider(resource=resource)
    otlp_exporter = OTLPLogExporter(
        endpoint=f"{telemetry_url}/v1/logs",
        headers=headers,
    )
    logger_provider.add_log_record_processor(SimpleLogRecordProcessor(otlp_exporter))
    set_logger_provider(logger_provider)
    _log_handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)


# def get_logger(name: str) -> logging.Logger:
#     """Get a logger configured with OTLP export if enabled."""
#     logger = logging.getLogger(name)
#     if _log_handler and check_flag("OTEL"):
#         logger.addHandler(_log_handler)
#     return logger


# def get_run_logger() -> Union[logging.Logger, logging.LoggerAdapter]:
#     """Get a Prefect run logger configured with OTLP export if enabled."""
#     import prefect

#     logger = prefect.get_run_logger()

#     if not _log_handler or not check_flag("OTEL"):
#         return logger

#     if isinstance(logger, logging.LoggerAdapter):
#         assert isinstance(logger.logger, logging.Logger)
#         logger.logger.addHandler(_log_handler)
#     else:
#         logger.addHandler(_log_handler)
#     return logger
