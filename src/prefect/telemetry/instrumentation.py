import logging
import os
import re
from typing import TYPE_CHECKING
from urllib.parse import urljoin
from uuid import UUID

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

from .logging import set_log_handler
from .processors import InFlightSpanProcessor
from .services import QueueingLogExporter, QueueingSpanExporter

if TYPE_CHECKING:
    from opentelemetry.sdk._logs import LoggerProvider

UUID_REGEX = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

ACCOUNTS_PREFIX = "accounts/"
ACCOUNT_ID_REGEX = f"{ACCOUNTS_PREFIX}{UUID_REGEX}"

WORKSPACES_PREFIX = "workspaces/"
WORKSPACE_ID_REGEX = f"{WORKSPACES_PREFIX}{UUID_REGEX}"


def extract_account_and_workspace_id(url: str) -> tuple[UUID, UUID]:
    account_id, workspace_id = None, None

    if res := re.search(ACCOUNT_ID_REGEX, url):
        account_id = UUID(res.group().removeprefix(ACCOUNTS_PREFIX))

    if res := re.search(WORKSPACE_ID_REGEX, url):
        workspace_id = UUID(res.group().removeprefix(WORKSPACES_PREFIX))

    if account_id and workspace_id:
        return account_id, workspace_id

    raise ValueError(
        f"Could not extract account and workspace id from API url: {url!r}"
    )


def _url_join(base_url: str, path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def setup_exporters(
    api_url: str, api_key: str
) -> "tuple[TracerProvider, MeterProvider, LoggerProvider]":
    account_id, workspace_id = extract_account_and_workspace_id(api_url)
    telemetry_url = _url_join(api_url, "telemetry/")

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

    trace_provider = _setup_trace_provider(resource, headers, telemetry_url)
    meter_provider = _setup_meter_provider(resource, headers, telemetry_url)
    logger_provider = _setup_logger_provider(resource, headers, telemetry_url)

    return trace_provider, meter_provider, logger_provider


def _setup_trace_provider(
    resource: Resource, headers: dict[str, str], telemetry_url: str
) -> TracerProvider:
    trace_provider = TracerProvider(resource=resource)
    queueing_span_exporter = QueueingSpanExporter.instance(
        _url_join(telemetry_url, "v1/traces"), tuple(headers.items())
    )
    trace_provider.add_span_processor(InFlightSpanProcessor(queueing_span_exporter))
    trace.set_tracer_provider(trace_provider)

    return trace_provider


def _setup_meter_provider(
    resource: Resource, headers: dict[str, str], telemetry_url: str
) -> MeterProvider:
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(  # pyright: ignore[reportArgumentType] `preferred_temporality` and `preferred_aggregation` default to `None`, but otel's typing doesn't include it
            endpoint=_url_join(telemetry_url, "v1/metrics"),
            headers=headers,
        )
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    return meter_provider


def _setup_logger_provider(
    resource: Resource, headers: dict[str, str], telemetry_url: str
) -> LoggerProvider:
    logger_provider = LoggerProvider(resource=resource)  # pyright: ignore[reportArgumentType] `multi_log_record_processor` defaults to `None` but otel's typing doesn't include it
    queueing_log_exporter = QueueingLogExporter.instance(
        _url_join(telemetry_url, "v1/logs"), tuple(headers.items())
    )
    logger_provider.add_log_record_processor(
        SimpleLogRecordProcessor(queueing_log_exporter)
    )
    set_logger_provider(logger_provider)
    log_handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)

    set_log_handler(log_handler)

    return logger_provider
