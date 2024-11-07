import os
from uuid import UUID

import pytest
from opentelemetry import metrics, trace
from opentelemetry._logs._internal import get_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider

from prefect.telemetry.bootstrap import setup_telemetry
from prefect.telemetry.instrumentation import extract_account_and_workspace_id
from prefect.telemetry.logging import get_log_handler
from prefect.telemetry.processors import InFlightSpanProcessor


def test_extract_account_and_workspace_id_valid_url(
    telemetry_account_id: UUID, telemetry_workspace_id: UUID
):
    url = (
        f"https://api.prefect.cloud/api/accounts/{telemetry_account_id}/"
        f"workspaces/{telemetry_workspace_id}"
    )
    account_id, workspace_id = extract_account_and_workspace_id(url)
    assert account_id == telemetry_account_id
    assert workspace_id == telemetry_workspace_id


@pytest.mark.parametrize(
    "url",
    [
        "https://api.prefect.cloud/api/invalid",
        "https://api.prefect.cloud/api/accounts/invalid-uuid/workspaces/22222222-2222-2222-2222-222222222222",
        "https://api.prefect.cloud/api/accounts/22222222-2222-2222-2222-222222222222/invalid",
        "https://api.prefect.cloud/api/workspaces/22222222-2222-2222-2222-222222222222",
    ],
)
def test_extract_account_and_workspace_id_invalid_urls(url):
    with pytest.raises(
        ValueError,
        match=f"Could not extract account and workspace id from API url: {url!r}",
    ):
        extract_account_and_workspace_id(url)


def test_telemetry_disabled(disable_telemetry):
    trace_provider, meter_provider, logger_provider = setup_telemetry()

    assert trace_provider is None
    assert meter_provider is None
    assert logger_provider is None


def test_non_cloud_server(hosted_server_with_telemetry_enabled):
    trace_provider, meter_provider, logger_provider = setup_telemetry()

    assert trace_provider is None
    assert meter_provider is None
    assert logger_provider is None


def test_trace_provider(
    enable_telemetry: None, telemetry_account_id: UUID, telemetry_workspace_id: UUID
):
    trace_provider, _, _ = setup_telemetry()

    assert isinstance(trace_provider, TracerProvider)

    resource_attributes = {
        k: v
        for k, v in trace_provider.resource.attributes.items()
        if not k.startswith("telemetry.sdk")
    }

    assert resource_attributes == {
        "service.name": "prefect",
        "service.instance.id": os.uname().nodename,
        "prefect.account": str(telemetry_account_id),
        "prefect.workspace": str(telemetry_workspace_id),
    }

    span_processor = trace_provider._active_span_processor._span_processors[0]

    assert isinstance(span_processor, InFlightSpanProcessor)
    assert (
        span_processor.span_exporter._endpoint  # type: ignore
        == (
            f"https://api.prefect.cloud/api/accounts/{telemetry_account_id}/"
            f"workspaces/{telemetry_workspace_id}/telemetry/v1/traces"
        )
    )

    assert trace.get_tracer_provider() == trace_provider


def test_meter_provider(
    enable_telemetry: None, telemetry_account_id: UUID, telemetry_workspace_id: UUID
):
    _, meter_provider, _ = setup_telemetry()
    assert isinstance(meter_provider, MeterProvider)

    metric_reader = list(meter_provider._all_metric_readers)[0]
    exporter = metric_reader._exporter
    assert isinstance(metric_reader, PeriodicExportingMetricReader)
    assert isinstance(exporter, OTLPMetricExporter)

    resource_attributes = {
        k: v
        for k, v in meter_provider._sdk_config.resource.attributes.items()
        if not k.startswith("telemetry.sdk")
    }

    assert resource_attributes == {
        "service.name": "prefect",
        "service.instance.id": os.uname().nodename,
        "prefect.account": str(telemetry_account_id),
        "prefect.workspace": str(telemetry_workspace_id),
    }

    assert (
        metric_reader._exporter._endpoint  # type: ignore
        == (
            f"https://api.prefect.cloud/api/accounts/{telemetry_account_id}/"
            f"workspaces/{telemetry_workspace_id}/telemetry/v1/metrics"
        )
    )

    assert metrics.get_meter_provider() == meter_provider


def test_logger_provider(
    enable_telemetry: None, telemetry_account_id: UUID, telemetry_workspace_id: UUID
):
    _, _, logger_provider = setup_telemetry()

    assert isinstance(logger_provider, LoggerProvider)

    processor = list(
        logger_provider._multi_log_record_processor._log_record_processors
    )[0]
    exporter = processor._exporter  # type: ignore

    assert isinstance(processor, SimpleLogRecordProcessor)
    assert isinstance(exporter, OTLPLogExporter)

    assert (
        exporter._endpoint  # type: ignore
        == (
            f"https://api.prefect.cloud/api/accounts/{telemetry_account_id}/"
            f"workspaces/{telemetry_workspace_id}/telemetry/v1/logs"
        )
    )

    assert get_logger_provider() == logger_provider

    log_handler = get_log_handler()
    assert isinstance(log_handler, LoggingHandler)
    assert log_handler._logger_provider == logger_provider
