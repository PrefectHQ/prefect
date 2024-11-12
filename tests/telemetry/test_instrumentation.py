import os
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

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
from opentelemetry.sdk.trace.export import InMemorySpanExporter

from prefect import flow, task
from prefect.client.schemas import TaskRun
from prefect.states import Completed, Running
from prefect.task_engine import AsyncTaskRunEngine, digest_task_inputs
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


class TestTaskRunInstrumentation:
    @task
    def test_task(x: int, y: int):
        return x + y

    @task
    def returns_4():
        return 4

    def test_digest_task_inputs(self):
        inputs = {"x": 1, "y": 2}
        parameters = {"x": int, "y": int}
        otel_params, otel_inputs = digest_task_inputs(inputs, parameters)
        assert otel_params == {
            "prefect.run.parameter.x": "int",
            "prefect.run.parameter.y": "int",
        }
        assert otel_inputs == []

    def test_linked_parameters(self):
        trace_provider, _, _ = setup_telemetry()
        tracer = trace_provider.get_tracer(__name__)
        with tracer.start_as_current_span("test_task"):
            self.test_task(x=self.returns_4(), y=2)


@pytest.fixture
def mock_tracer():
    trace_provider, _, _ = setup_telemetry()
    span_exporter = InMemorySpanExporter()
    span_processor = InFlightSpanProcessor(span_exporter)
    trace_provider.add_span_processor(span_processor)
    trace.set_tracer_provider(trace_provider)
    return trace.get_tracer("prefect.test")


@pytest.fixture
async def task_run_engine(mock_tracer):
    @task
    async def test_task(x: int, y: int):
        return x + y

    task_run = TaskRun(
        id=uuid4(),
        task_key="test_task",
        flow_run_id=uuid4(),
        state=Running(),
        dynamic_key="test_task-1",
    )

    engine = AsyncTaskRunEngine(
        task=test_task,
        task_run=task_run,
        parameters={"x": 1, "y": 2},
        _tracer=mock_tracer,
    )
    return engine


@pytest.mark.asyncio
async def test_span_creation(task_run_engine, mock_tracer):
    async with task_run_engine.start():
        assert task_run_engine._span is not None
        assert task_run_engine._span.name == task_run_engine.task_run.name
        assert task_run_engine._span.attributes["prefect.run.type"] == "task"
        assert task_run_engine._span.attributes["prefect.run.id"] == str(
            task_run_engine.task_run.id
        )


@pytest.mark.asyncio
async def test_span_attributes(task_run_engine):
    async with task_run_engine.start():
        assert "prefect.run.parameter.x" in task_run_engine._span.attributes
        assert "prefect.run.parameter.y" in task_run_engine._span.attributes
        assert task_run_engine._span.attributes["prefect.run.parameter.x"] == "int"
        assert task_run_engine._span.attributes["prefect.run.parameter.y"] == "int"


@pytest.mark.asyncio
async def test_span_events(task_run_engine):
    async with task_run_engine.start():
        await task_run_engine.set_state(Running())
        await task_run_engine.set_state(Completed())

    events = task_run_engine._span.events
    assert len(events) == 2
    assert events[0].name == "Running"
    assert events[1].name == "Completed"


@pytest.mark.asyncio
async def test_span_status_on_success(task_run_engine):
    async with task_run_engine.start():
        async with task_run_engine.run_context():
            await task_run_engine.handle_success(3, Mock())

    assert task_run_engine._span.status.status_code == trace.StatusCode.OK


@pytest.mark.asyncio
async def test_span_status_on_failure(task_run_engine):
    async with task_run_engine.start():
        async with task_run_engine.run_context():
            await task_run_engine.handle_exception(ValueError("Test error"))

    assert task_run_engine._span.status.status_code == trace.StatusCode.ERROR
    assert "Test error" in task_run_engine._span.status.description


@pytest.mark.asyncio
async def test_span_exception_recording(task_run_engine):
    test_exception = ValueError("Test error")
    async with task_run_engine.start():
        async with task_run_engine.run_context():
            await task_run_engine.handle_exception(test_exception)

    events = task_run_engine._span.events
    assert any(event.name == "exception" for event in events)
    exception_event = next(event for event in events if event.name == "exception")
    assert exception_event.attributes["exception.type"] == "ValueError"
    assert exception_event.attributes["exception.message"] == "Test error"


@pytest.mark.asyncio
async def test_span_links(task_run_engine):
    # Simulate a parent task run
    parent_task_run_id = uuid4()
    task_run_engine.task_run.task_inputs = {"x": [{"id": parent_task_run_id}], "y": [2]}

    async with task_run_engine.start():
        pass

    assert len(task_run_engine._span.links) == 1
    link = task_run_engine._span.links[0]
    assert link.context.trace_id == int(parent_task_run_id)
    assert link.attributes["prefect.run.id"] == str(parent_task_run_id)


@pytest.mark.asyncio
async def test_flow_run_labels(task_run_engine):
    @flow
    async def test_flow():
        return await task_run_engine.task()

    with patch("prefect.context.FlowRunContext.get") as mock_flow_run_context:
        mock_flow_run_context.return_value.flow_run.labels = {"env": "test"}
        async with task_run_engine.start():
            pass

    assert task_run_engine._span.attributes["env"] == "test"
