import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict
from urllib.parse import urljoin
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
from opentelemetry.trace import (
    Status,
    StatusCode,
    Tracer,
    get_tracer,
)

import prefect
from prefect.client.schemas import TaskRun
from prefect.client.schemas.objects import State

from .logging import set_log_handler
from .processors import InFlightSpanProcessor

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
) -> tuple[TracerProvider, MeterProvider, "LoggerProvider"]:
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
    otlp_span_exporter = OTLPSpanExporter(
        endpoint=_url_join(telemetry_url, "v1/traces"),
        headers=headers,
    )
    trace_provider.add_span_processor(InFlightSpanProcessor(otlp_span_exporter))
    trace.set_tracer_provider(trace_provider)

    return trace_provider


def _setup_meter_provider(
    resource: Resource, headers: dict[str, str], telemetry_url: str
) -> MeterProvider:
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
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
    logger_provider = LoggerProvider(resource=resource)
    otlp_exporter = OTLPLogExporter(
        endpoint=_url_join(telemetry_url, "v1/logs"),
        headers=headers,
    )
    logger_provider.add_log_record_processor(SimpleLogRecordProcessor(otlp_exporter))
    set_logger_provider(logger_provider)
    log_handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)

    set_log_handler(log_handler)

    return logger_provider


@dataclass
class RunTelemetry:
    _tracer: Tracer = field(
        default_factory=lambda: get_tracer("prefect", prefect.__version__)
    )
    _span = None

    def start_span(
        self,
        task_run: TaskRun,
        parameters: Dict[str, Any] = {},
        labels: Dict[str, Any] = {},
    ):
        parameter_attributes = {
            f"prefect.run.parameter.{k}": type(v).__name__
            for k, v in parameters.items()
        }
        self._span = self._tracer.start_span(
            name=task_run.name,
            attributes={
                "prefect.run.type": "task",
                "prefect.run.id": str(task_run.id),
                "prefect.tags": task_run.tags,
                **parameter_attributes,
                **labels,
            },
        )

    def end_span_on_success(self, terminal_message: str):
        if self._span:
            self._span.set_status(Status(StatusCode.OK), terminal_message)
            self._span.end(time.time_ns())
            self._span = None

    def end_span_on_failure(self, terminal_message: str):
        if self._span:
            self._span.set_status(Status(StatusCode.ERROR, terminal_message))
            self._span.end(time.time_ns())
            self._span = None

    def record_exception(self, exc: Exception):
        if self._span:
            self._span.record_exception(exc)

    def update_state(self, new_state: State):
        if self._span:
            self._span.add_event(
                new_state.name,
                {
                    "prefect.state.message": new_state.message or "",
                    "prefect.state.type": new_state.type,
                    "prefect.state.name": new_state.name or new_state.type,
                    "prefect.state.id": str(new_state.id),
                },
            )
