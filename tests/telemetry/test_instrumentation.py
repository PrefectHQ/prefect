import os
from unittest.mock import patch
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

from prefect import flow, task
from prefect.client.schemas import TaskRun
from prefect.states import Running
from prefect.task_engine import AsyncTaskRunEngine, run_task_async
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
    def assert_has_attributes(self, span, **expected_attributes):
        """Helper method to assert span has expected attributes"""
        for key, value in expected_attributes.items():
            assert (
                span.attributes.get(key) == value
            ), f"Expected {key}={value}, got {span.attributes.get(key)}"

    @pytest.fixture
    async def task_run_engine(self, instrumentation):
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
            _tracer=instrumentation.tracer_provider.get_tracer("prefect.test"),
        )
        return engine

    @pytest.mark.asyncio
    async def test_span_creation(self, task_run_engine, instrumentation):
        @task
        async def test_task(x: int, y: int):
            return x + y

        task_run_id = uuid4()
        await run_task_async(
            test_task, task_run_id=task_run_id, parameters={"x": 1, "y": 2}
        )

        spans = instrumentation.get_finished_spans()
        assert len(spans) == 1
        self.assert_has_attributes(
            spans[0], **{"prefect.run.id": str(task_run_id), "prefect.run.type": "task"}
        )
        assert spans[0].name == "test_task"

    @pytest.mark.asyncio
    async def test_span_attributes(self, task_run_engine, instrumentation):
        @task
        async def test_task(x: int, y: int):
            return x + y

        task_run_id = uuid4()
        await run_task_async(
            test_task, task_run_id=task_run_id, parameters={"x": 1, "y": 2}
        )

        spans = instrumentation.get_finished_spans()
        assert len(spans) == 1
        self.assert_has_attributes(
            spans[0],
            **{
                "prefect.run.id": str(task_run_id),
                "prefect.run.type": "task",
                "prefect.run.parameter.x": "int",
                "prefect.run.parameter.y": "int",
            },
        )
        assert spans[0].name == "test_task"

    @pytest.mark.asyncio
    async def test_span_events(self, task_run_engine, instrumentation):
        @task
        async def test_task(x: int, y: int):
            return x + y

        task_run_id = uuid4()
        await run_task_async(
            test_task, task_run_id=task_run_id, parameters={"x": 1, "y": 2}
        )

        spans = instrumentation.get_finished_spans()
        events = spans[0].events
        assert len(events) == 2
        assert events[0].name == "Running"
        assert events[1].name == "Completed"

    @pytest.mark.asyncio
    async def test_span_status_on_success(self, task_run_engine, instrumentation):
        @task
        async def test_task(x: int, y: int):
            return x + y

        task_run_id = uuid4()
        await run_task_async(
            test_task, task_run_id=task_run_id, parameters={"x": 1, "y": 2}
        )

        spans = instrumentation.get_finished_spans()
        assert len(spans) == 1

        assert spans[0].status.status_code == trace.StatusCode.OK

    @pytest.mark.asyncio
    async def test_span_status_on_failure(self, task_run_engine, instrumentation):
        @task
        async def test_task(x: int, y: int):
            raise ValueError("Test error")

        task_run_id = uuid4()
        with pytest.raises(ValueError, match="Test error"):
            await run_task_async(
                test_task, task_run_id=task_run_id, parameters={"x": 1, "y": 2}
            )

        spans = instrumentation.get_finished_spans()
        assert len(spans) == 1

        assert spans[0].status.status_code == trace.StatusCode.ERROR
        assert "Test error" in spans[0].status.description

    @pytest.mark.asyncio
    async def test_span_exception_recording(self, task_run_engine, instrumentation):
        @task
        async def test_task(x: int, y: int):
            raise Exception("Test error")

        task_run_id = uuid4()

        with pytest.raises(Exception, match="Test error"):
            await run_task_async(
                test_task, task_run_id=task_run_id, parameters={"x": 1, "y": 2}
            )

        spans = instrumentation.get_finished_spans()
        assert len(spans) == 1

        events = spans[0].events

        assert any(event.name == "exception" for event in events)
        exception_event = next(event for event in events if event.name == "exception")
        assert exception_event.attributes["exception.type"] == "Exception"
        assert exception_event.attributes["exception.message"] == "Test error"

    @pytest.mark.asyncio
    async def test_flow_run_labels(self, task_run_engine, instrumentation):
        """Test that flow run labels are propagated to task spans"""

        @task
        async def child_task():
            return 1

        @flow
        async def parent_flow():
            return await child_task()

        with patch("prefect.task_engine.get_labels_from_context") as mock_get:
            mock_get.return_value = {"env": "test", "team": "engineering"}
            await parent_flow()

        spans = instrumentation.get_finished_spans()
        task_spans = [
            span for span in spans if span.attributes.get("prefect.run.type") == "task"
        ]
        assert len(task_spans) == 1

        self.assert_has_attributes(
            task_spans[0],
            **{"prefect.run.type": "task", "env": "test", "team": "engineering"},
        )
