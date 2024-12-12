import os
from typing import Literal
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
from tests.telemetry.instrumentation_tester import InstrumentationTester

import prefect
from prefect import flow, task
from prefect.client.orchestration import SyncPrefectClient
from prefect.context import FlowRunContext
from prefect.task_engine import (
    run_task_async,
    run_task_sync,
)
from prefect.telemetry.bootstrap import setup_telemetry
from prefect.telemetry.instrumentation import (
    extract_account_and_workspace_id,
)
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


class TestFlowRunInstrumentation:
    @pytest.fixture(params=["async", "sync"])
    async def engine_type(
        self, request: pytest.FixtureRequest
    ) -> Literal["async", "sync"]:
        return request.param

    async def test_flow_run_creates_and_stores_otel_traceparent(
        self,
        engine_type: Literal["async", "sync"],
        instrumentation: InstrumentationTester,
        sync_prefect_client: SyncPrefectClient,
    ):
        """Test that when no parent traceparent exists, the flow run stores its own span's traceparent"""

        @flow(name="child-flow")
        async def async_child_flow() -> str:
            return "hello from child"

        @flow(name="child-flow")
        def sync_child_flow() -> str:
            return "hello from child"

        @flow(name="parent-flow")
        async def async_parent_flow() -> str:
            return await async_child_flow()

        @flow(name="parent-flow")
        def sync_parent_flow() -> str:
            return sync_child_flow()

        if engine_type == "async":
            await async_parent_flow()
        else:
            sync_parent_flow()

        spans = instrumentation.get_finished_spans()

        next(
            span
            for span in spans
            if span.attributes.get("prefect.flow.name") == "parent-flow"
        )
        child_span = next(
            span
            for span in spans
            if span.attributes.get("prefect.flow.name") == "child-flow"
        )

        # Get the child flow run
        child_flow_run_id = child_span.attributes.get("prefect.run.id")
        child_flow_run = sync_prefect_client.read_flow_run(UUID(child_flow_run_id))

        # Verify the child flow run has its span's traceparent in its labels
        assert "__OTEL_TRACEPARENT" in child_flow_run.labels
        assert child_flow_run.labels["__OTEL_TRACEPARENT"].startswith("00-")
        trace_id_hex = child_flow_run.labels["__OTEL_TRACEPARENT"].split("-")[1]
        assert int(trace_id_hex, 16) == child_span.context.trace_id

    async def test_flow_run_propagates_otel_traceparent_to_subflow(
        self,
        engine_type: Literal["async", "sync"],
        instrumentation: InstrumentationTester,
    ):
        """Test that OTEL traceparent gets propagated from parent flow to child flow"""

        @flow(name="child-flow")
        async def async_child_flow() -> str:
            return "hello from child"

        @flow(name="child-flow")
        def sync_child_flow() -> str:
            return "hello from child"

        @flow(name="parent-flow")
        async def async_parent_flow() -> str:
            # Set OTEL context in the parent flow's labels
            flow_run = FlowRunContext.get().flow_run
            mock_traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
            flow_run.labels["__OTEL_TRACEPARENT"] = mock_traceparent
            return await async_child_flow()

        @flow(name="parent-flow")
        def sync_parent_flow() -> str:
            # Set OTEL context in the parent flow's labels
            flow_run = FlowRunContext.get().flow_run
            mock_traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
            flow_run.labels["__OTEL_TRACEPARENT"] = mock_traceparent
            return sync_child_flow()

        parent_flow = async_parent_flow if engine_type == "async" else sync_parent_flow
        await parent_flow() if engine_type == "async" else parent_flow()

        spans = instrumentation.get_finished_spans()

        parent_span = next(
            span
            for span in spans
            if span.attributes.get("prefect.flow.name") == "parent-flow"
        )
        child_span = next(
            span
            for span in spans
            if span.attributes.get("prefect.flow.name") == "child-flow"
        )

        assert parent_span is not None
        assert child_span is not None
        assert child_span.context.trace_id == parent_span.context.trace_id

    async def test_flow_run_instrumentation(
        self,
        engine_type: Literal["async", "sync"],
        instrumentation: InstrumentationTester,
    ):
        @flow(name="instrumented-flow")
        async def async_flow() -> str:
            return 42

        @flow(name="instrumented-flow")
        def sync_flow() -> str:
            return 42

        test_flow = async_flow if engine_type == "async" else sync_flow
        await test_flow() if engine_type == "async" else test_flow()

        spans = instrumentation.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span is not None
        instrumentation.assert_span_instrumented_for(span, prefect)

        instrumentation.assert_has_attributes(
            span,
            {
                "prefect.flow.name": "instrumented-flow",
                "prefect.run.type": "flow",
            },
        )

    async def test_flow_run_inherits_parent_labels(
        self,
        engine_type: Literal["async", "sync"],
        instrumentation: InstrumentationTester,
        sync_prefect_client: SyncPrefectClient,
    ):
        """Test that parent flow labels get propagated to child flow spans"""

        @flow(name="child-flow")
        async def async_child_flow() -> str:
            return "hello from child"

        @flow(name="child-flow")
        def sync_child_flow() -> str:
            return "hello from child"

        @flow(name="parent-flow")
        async def async_parent_flow() -> str:
            # Set custom labels in parent flow
            flow_run = FlowRunContext.get().flow_run
            flow_run.labels.update(
                {"test.label": "test-value", "environment": "testing"}
            )
            return await async_child_flow()

        @flow(name="parent-flow")
        def sync_parent_flow() -> str:
            # Set custom labels in parent flow
            flow_run = FlowRunContext.get().flow_run
            flow_run.labels.update(
                {"test.label": "test-value", "environment": "testing"}
            )
            return sync_child_flow()

        if engine_type == "async":
            state = await async_parent_flow(return_state=True)
        else:
            state = sync_parent_flow(return_state=True)

        spans = instrumentation.get_finished_spans()
        child_spans = [
            span
            for span in spans
            if span.attributes.get("prefect.flow.name") == "child-flow"
        ]
        assert len(child_spans) == 1

        # Get the parent flow run
        parent_flow_run = sync_prefect_client.read_flow_run(
            state.state_details.flow_run_id
        )

        # Verify the child span has the parent flow's labels
        instrumentation.assert_has_attributes(
            child_spans[0],
            {
                **parent_flow_run.labels,
                "prefect.run.type": "flow",
                "prefect.flow.name": "child-flow",
            },
        )


class TestTaskRunInstrumentation:
    @pytest.fixture(params=["async", "sync"])
    async def engine_type(
        self, request: pytest.FixtureRequest
    ) -> Literal["async", "sync"]:
        return request.param

    async def run_task(self, task, task_run_id, parameters, engine_type):
        if engine_type == "async":
            return await run_task_async(
                task, task_run_id=task_run_id, parameters=parameters
            )
        else:
            return run_task_sync(task, task_run_id=task_run_id, parameters=parameters)

    async def test_span_creation(
        self,
        engine_type: Literal["async", "sync"],
        instrumentation: InstrumentationTester,
    ):
        @task
        async def async_task(x: int, y: int):
            return x + y

        @task
        def sync_task(x: int, y: int):
            return x + y

        task_fn = async_task if engine_type == "async" else sync_task
        task_run_id = uuid4()

        await self.run_task(
            task_fn,
            task_run_id=task_run_id,
            parameters={"x": 1, "y": 2},
            engine_type=engine_type,
        )

        spans = instrumentation.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]

        instrumentation.assert_has_attributes(
            span, {"prefect.run.id": str(task_run_id), "prefect.run.type": "task"}
        )
        assert spans[0].name == task_fn.name

    async def test_span_attributes(
        self,
        engine_type: Literal["async", "sync"],
        instrumentation: InstrumentationTester,
    ):
        @task
        async def async_task(x: int, y: int):
            return x + y

        @task
        def sync_task(x: int, y: int):
            return x + y

        task_fn = async_task if engine_type == "async" else sync_task
        task_run_id = uuid4()

        await self.run_task(
            task_fn,
            task_run_id=task_run_id,
            parameters={"x": 1, "y": 2},
            engine_type=engine_type,
        )

        spans = instrumentation.get_finished_spans()
        assert len(spans) == 1
        instrumentation.assert_has_attributes(
            spans[0],
            {
                "prefect.run.id": str(task_run_id),
                "prefect.run.type": "task",
                "prefect.run.parameter.x": "int",
                "prefect.run.parameter.y": "int",
            },
        )
        assert spans[0].name == task_fn.__name__

    async def test_span_events(
        self,
        engine_type: Literal["async", "sync"],
        instrumentation: InstrumentationTester,
    ):
        @task
        async def async_task(x: int, y: int):
            return x + y

        @task
        def sync_task(x: int, y: int):
            return x + y

        task_fn = async_task if engine_type == "async" else sync_task
        task_run_id = uuid4()

        await self.run_task(
            task_fn,
            task_run_id=task_run_id,
            parameters={"x": 1, "y": 2},
            engine_type=engine_type,
        )

        spans = instrumentation.get_finished_spans()
        events = spans[0].events
        assert len(events) == 2
        assert events[0].name == "Running"
        assert events[1].name == "Completed"

    async def test_span_status_on_success(
        self,
        engine_type: Literal["async", "sync"],
        instrumentation: InstrumentationTester,
    ):
        @task
        async def async_task(x: int, y: int):
            return x + y

        @task
        def sync_task(x: int, y: int):
            return x + y

        task_fn = async_task if engine_type == "async" else sync_task
        task_run_id = uuid4()

        await self.run_task(
            task_fn,
            task_run_id=task_run_id,
            parameters={"x": 1, "y": 2},
            engine_type=engine_type,
        )

        spans = instrumentation.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == trace.StatusCode.OK

    async def test_span_status_on_failure(
        self,
        engine_type: Literal["async", "sync"],
        instrumentation: InstrumentationTester,
    ):
        @task
        async def async_task(x: int, y: int):
            raise ValueError("Test error")

        @task
        def sync_task(x: int, y: int):
            raise ValueError("Test error")

        task_fn = async_task if engine_type == "async" else sync_task
        task_run_id = uuid4()

        with pytest.raises(ValueError, match="Test error"):
            await self.run_task(
                task_fn,
                task_run_id=task_run_id,
                parameters={"x": 1, "y": 2},
                engine_type=engine_type,
            )

        spans = instrumentation.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == trace.StatusCode.ERROR
        assert "Test error" in spans[0].status.description

    async def test_span_exception_recording(
        self,
        engine_type: Literal["async", "sync"],
        instrumentation: InstrumentationTester,
    ):
        @task
        async def async_task(x: int, y: int):
            raise Exception("Test error")

        @task
        def sync_task(x: int, y: int):
            raise Exception("Test error")

        task_fn = async_task if engine_type == "async" else sync_task
        task_run_id = uuid4()

        with pytest.raises(Exception, match="Test error"):
            await self.run_task(
                task_fn,
                task_run_id=task_run_id,
                parameters={"x": 1, "y": 2},
                engine_type=engine_type,
            )

        spans = instrumentation.get_finished_spans()
        assert len(spans) == 1

        events = spans[0].events
        assert any(event.name == "exception" for event in events)
        exception_event = next(event for event in events if event.name == "exception")
        assert exception_event.attributes["exception.type"] == "Exception"
        assert exception_event.attributes["exception.message"] == "Test error"

    async def test_flow_labels(
        self,
        engine_type: Literal["async", "sync"],
        instrumentation: InstrumentationTester,
        sync_prefect_client: SyncPrefectClient,
    ):
        """Test that parent flow ID gets propagated to task spans"""

        @task
        async def async_child_task():
            return 1

        @task
        def sync_child_task():
            return 1

        @flow
        async def async_parent_flow():
            return await async_child_task()

        @flow
        def sync_parent_flow():
            return sync_child_task()

        if engine_type == "async":
            state = await async_parent_flow(return_state=True)
        else:
            state = sync_parent_flow(return_state=True)

        spans = instrumentation.get_finished_spans()
        task_spans = [
            span for span in spans if span.attributes.get("prefect.run.type") == "task"
        ]
        assert len(task_spans) == 1

        assert state.state_details.flow_run_id is not None
        flow_run = sync_prefect_client.read_flow_run(state.state_details.flow_run_id)

        # Verify the task span has the parent flow's ID
        instrumentation.assert_has_attributes(
            task_spans[0], {**flow_run.labels, "prefect.run.type": "task"}
        )
