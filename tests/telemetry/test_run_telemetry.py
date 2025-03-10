from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

import pytest
from opentelemetry import trace
from tests.telemetry.instrumentation_tester import InstrumentationTester

import prefect
from prefect import flow, task
from prefect.client.orchestration import SyncPrefectClient
from prefect.flow_engine import run_flow_async, run_flow_sync
from prefect.flows import Flow
from prefect.settings import (
    PREFECT_CLOUD_ENABLE_ORCHESTRATION_TELEMETRY,
    temporary_settings,
)
from prefect.task_engine import run_task_async, run_task_sync
from prefect.telemetry.run_telemetry import LABELS_TRACEPARENT_KEY

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import ReadableSpan

    from prefect.client.schemas import FlowRun


def traceparent_from_span(span: "ReadableSpan") -> str:
    span_context = span.get_span_context()
    assert span_context is not None
    return f"00-{span_context.trace_id:032x}-{span_context.span_id:016x}-01"


def find_span_by_run_name(*spans: "ReadableSpan", run_name: str) -> "ReadableSpan":
    try:
        return next(
            span
            for span in spans
            if span.attributes and span.attributes.get("prefect.run.name") == run_name
        )
    except StopIteration:
        raise AssertionError(f"No span found with run name {run_name!r}")


async def run_flow(
    flow: Flow, flow_run: "FlowRun", engine_type: Literal["async", "sync"]
):
    if engine_type == "async":
        return await run_flow_async(flow, flow_run=flow_run)
    else:
        return run_flow_sync(flow, flow_run=flow_run)


async def run_task(task, task_run_id, parameters, engine_type):
    if engine_type == "async":
        return await run_task_async(
            task, task_run_id=task_run_id, parameters=parameters
        )
    else:
        return run_task_sync(task, task_run_id=task_run_id, parameters=parameters)


@pytest.fixture(params=["async", "sync"])
async def engine_type(request: pytest.FixtureRequest) -> Literal["async", "sync"]:
    return request.param


async def test_traceparent_propagates_from_server_side(
    engine_type: Literal["async", "sync"],
    instrumentation: InstrumentationTester,
    sync_prefect_client: SyncPrefectClient,
):
    """Test that when no parent traceparent exists, the flow run stores its own span's traceparent"""

    @flow
    async def my_async_flow():
        pass

    @flow
    def my_sync_flow():
        pass

    the_flow = my_async_flow if engine_type == "async" else my_sync_flow
    flow_run = sync_prefect_client.create_flow_run(the_flow)  # type: ignore

    # Give the flow run a traceparent. This can occur when the server has
    # already created a trace for the run, likely because it was Late.
    #
    # Trace ID: 314419354619557650326501540139523824930
    # Span ID: 5357380918965115138
    sync_prefect_client.update_flow_run_labels(
        flow_run.id,
        {
            LABELS_TRACEPARENT_KEY: "00-ec8af70b445d54387035c27eb182dd22-4a593d8fa95f1902-01"
        },
    )

    flow_run = sync_prefect_client.read_flow_run(flow_run.id)
    assert flow_run.labels[LABELS_TRACEPARENT_KEY] == (
        "00-ec8af70b445d54387035c27eb182dd22-4a593d8fa95f1902-01"
    )

    await run_flow(the_flow, flow_run=flow_run, engine_type=engine_type)

    spans = instrumentation.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    # Since the flow run is creating a new span it should also update its
    # labels with the newest traceparent.
    traceparent = traceparent_from_span(span)
    assert traceparent
    assert flow_run.labels[LABELS_TRACEPARENT_KEY] == traceparent

    span_context = span.get_span_context()
    assert span_context is not None
    assert span_context.trace_id == 314419354619557650326501540139523824930

    assert span.parent is not None
    assert span.parent.trace_id == 314419354619557650326501540139523824930
    assert span.parent.span_id == 5357380918965115138


async def test_flow_run_creates_and_stores_traceparent(
    engine_type: Literal["async", "sync"],
    instrumentation: InstrumentationTester,
    sync_prefect_client: SyncPrefectClient,
):
    @flow(flow_run_name="the-flow")
    async def async_flow():
        pass

    @flow(flow_run_name="the-flow")
    def sync_flow():
        pass

    await async_flow() if engine_type == "async" else sync_flow()

    spans = instrumentation.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    # Get the child flow run
    assert span.attributes is not None
    flow_run_id = span.attributes.get("prefect.run.id")
    assert flow_run_id is not None
    flow_run = sync_prefect_client.read_flow_run(UUID(str(flow_run_id)))

    assert LABELS_TRACEPARENT_KEY in flow_run.labels
    expected_traceparent = traceparent_from_span(span)
    assert flow_run.labels[LABELS_TRACEPARENT_KEY] == expected_traceparent


async def test_flow_run_instrumentation(
    engine_type: Literal["async", "sync"],
    instrumentation: InstrumentationTester,
):
    @flow(flow_run_name="instrumented-flow")
    async def async_flow() -> str:
        return "hello"

    @flow(flow_run_name="instrumented-flow")
    def sync_flow() -> str:
        return "hello"

    the_flow = async_flow if engine_type == "async" else sync_flow
    await the_flow() if engine_type == "async" else the_flow()

    spans = instrumentation.get_finished_spans()
    assert len(spans) == 1

    span = spans[0]
    assert span is not None
    instrumentation.assert_span_instrumented_for(span, prefect)

    instrumentation.assert_has_attributes(
        span,
        {
            "prefect.run.name": "instrumented-flow",
            "prefect.run.type": "flow",
        },
    )


async def test_task_span_creation(
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

    await run_task(
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

    await run_task(
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

    await run_task(
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


async def test_span_links(
    engine_type: Literal["async", "sync"],
    instrumentation: InstrumentationTester,
):
    @task(task_run_name="produces42")
    def produces42() -> int:
        return 42

    if engine_type == "async":

        @task(task_run_name="async_task")
        async def async_task(x: int, y: int):
            return x + y

        @flow(flow_run_name="async-flow")
        async def async_flow():
            await async_task(x=produces42.submit(), y=2)

        await async_flow()
    else:

        @task(task_run_name="sync_task")
        def sync_task(x: int, y: int):
            return x + y

        @flow(flow_run_name="sync-flow")
        def sync_flow():
            sync_task(x=produces42.submit(), y=2)

        sync_flow()

    spans = instrumentation.get_finished_spans()

    assert len(spans) == 3  # flow, producer, task

    flow_span = next(span for span in spans if span.name.endswith("-flow"))
    task_span = next(span for span in spans if span.name.endswith("_task"))
    producer_span = next(span for span in spans if span.name == "produces42")

    assert not flow_span.links
    assert not producer_span.links

    instrumentation.assert_has_attributes(
        task_span,
        {
            "prefect.run.parameter.x": "PrefectConcurrentFuture",
            "prefect.run.parameter.y": "int",
        },
    )

    assert len(task_span.links) == 1
    link = task_span.links[0]
    assert link.context.trace_id == producer_span.context.trace_id
    assert link.context.span_id == producer_span.context.span_id
    assert link.attributes == {
        "prefect.input.name": "x",
        "prefect.input.type": "int",
    }


async def test_span_links_wait_for_only(
    engine_type: Literal["async", "sync"],
    instrumentation: InstrumentationTester,
):
    """Regression test for https://github.com/PrefectHQ/prefect/issues/16708, where
    we are looking for the parameter name of a future that is only used for waiting"""

    @task(task_run_name="produces42")
    def produces42() -> int:
        return 42

    if engine_type == "async":

        @task(task_run_name="async_task")
        async def async_task():
            return "hi"

        @flow(flow_run_name="async-flow")
        async def async_flow():
            f = produces42.submit()
            await async_task(wait_for=[f])

        await async_flow()
    else:

        @task(task_run_name="sync_task")
        def sync_task():
            return "hi"

        @flow(flow_run_name="sync-flow")
        def sync_flow():
            f = produces42.submit()
            sync_task(wait_for=[f])

        sync_flow()

    spans = instrumentation.get_finished_spans()

    assert len(spans) == 3  # flow, producer, task

    flow_span = next(span for span in spans if span.name.endswith("-flow"))
    task_span = next(span for span in spans if span.name.endswith("_task"))
    producer_span = next(span for span in spans if span.name == "produces42")

    assert not flow_span.links
    assert not producer_span.links

    assert len(task_span.links) == 1
    link = task_span.links[0]
    assert link.context.trace_id == producer_span.context.trace_id
    assert link.context.span_id == producer_span.context.span_id
    assert link.attributes == {}


async def test_span_status_on_success(
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

    await run_task(
        task_fn,
        task_run_id=task_run_id,
        parameters={"x": 1, "y": 2},
        engine_type=engine_type,
    )

    spans = instrumentation.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].status.status_code == trace.StatusCode.OK


async def test_span_status_on_failure(
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
        await run_task(
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
        await run_task(
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


async def test_nested_flow_task_task(
    engine_type: Literal["async", "sync"],
    instrumentation: InstrumentationTester,
    sync_prefect_client: SyncPrefectClient,
):
    @flow(flow_run_name="parent-flow")
    async def my_async_flow():
        await async_child_task()

    @flow(flow_run_name="parent-flow")
    def my_sync_flow():
        sync_child_task()

    @task(task_run_name="child-task")
    def sync_child_task():
        sync_grandchild_task()

    @task(task_run_name="child-task")
    async def async_child_task():
        await async_grandchild_task()

    @task(task_run_name="grandchild-task")
    def sync_grandchild_task():
        pass

    @task(task_run_name="grandchild-task")
    async def async_grandchild_task():
        pass

    the_flow = my_async_flow if engine_type == "async" else my_sync_flow
    flow_run = sync_prefect_client.create_flow_run(the_flow)  # type: ignore

    await run_flow(the_flow, flow_run=flow_run, engine_type=engine_type)

    spans = instrumentation.get_finished_spans()
    assert len(spans) == 3

    parent_span = find_span_by_run_name(*spans, run_name="parent-flow")
    assert parent_span.context is not None

    child_span = find_span_by_run_name(*spans, run_name="child-task")
    assert child_span.context is not None

    grandchild_span = find_span_by_run_name(*spans, run_name="grandchild-task")
    assert grandchild_span.context is not None

    assert parent_span.parent is None
    assert (
        parent_span.context.trace_id
        == child_span.context.trace_id
        == grandchild_span.context.trace_id
    )

    # The child span should have the `parent_span` as its parent
    assert child_span.parent is not None
    assert child_span.parent.span_id == parent_span.context.span_id

    # The grandchild span should have the `child_span` as its parent
    assert grandchild_span.parent is not None
    assert grandchild_span.parent.span_id == child_span.context.span_id


async def test_nested_flow_task_flow(
    engine_type: Literal["async", "sync"],
    instrumentation: InstrumentationTester,
    sync_prefect_client: SyncPrefectClient,
):
    @flow(flow_run_name="parent-flow")
    async def my_async_flow():
        await async_child_task()

    @flow(flow_run_name="parent-flow")
    def my_sync_flow():
        sync_child_task()

    @task(task_run_name="child-task")
    def sync_child_task():
        sync_grandchild_flow()

    @task(task_run_name="child-task")
    async def async_child_task():
        await async_grandchild_flow()

    @flow(flow_run_name="grandchild-flow")
    def sync_grandchild_flow():
        pass

    @flow(flow_run_name="grandchild-flow")
    async def async_grandchild_flow():
        pass

    the_flow = my_async_flow if engine_type == "async" else my_sync_flow
    flow_run = sync_prefect_client.create_flow_run(the_flow)  # type: ignore

    await run_flow(the_flow, flow_run=flow_run, engine_type=engine_type)

    spans = instrumentation.get_finished_spans()
    assert len(spans) == 3

    parent_span = find_span_by_run_name(*spans, run_name="parent-flow")
    assert parent_span.context is not None

    child_span = find_span_by_run_name(*spans, run_name="child-task")
    assert child_span.context is not None

    grandchild_span = find_span_by_run_name(*spans, run_name="grandchild-flow")
    assert grandchild_span.context is not None

    assert parent_span.parent is None
    assert (
        parent_span.context.trace_id
        == child_span.context.trace_id
        == grandchild_span.context.trace_id
    )

    # The child span should have the `parent_span` as its parent
    assert child_span.parent is not None
    assert child_span.parent.span_id == parent_span.context.span_id

    # The grandchild span should have the `child_span` as its parent
    assert grandchild_span.parent is not None
    assert grandchild_span.parent.span_id == child_span.context.span_id


async def test_nested_task_flow_task(
    engine_type: Literal["async", "sync"],
    instrumentation: InstrumentationTester,
):
    @task(task_run_name="parent-task")
    async def async_parent_task():
        await async_child_flow()

    @task(task_run_name="parent-task")
    def sync_parent_task():
        sync_child_flow()

    @flow(flow_run_name="child-flow")
    def sync_child_flow():
        sync_grandchild_task()

    @flow(flow_run_name="child-flow")
    async def async_child_flow():
        await async_grandchild_task()

    @task(task_run_name="grandchild-task")
    def sync_grandchild_task():
        pass

    @task(task_run_name="grandchild-task")
    async def async_grandchild_task():
        pass

    the_task = async_parent_task if engine_type == "async" else sync_parent_task

    await run_task(
        the_task, task_run_id=uuid4(), parameters={}, engine_type=engine_type
    )

    spans = instrumentation.get_finished_spans()
    assert len(spans) == 3

    parent_span = find_span_by_run_name(*spans, run_name="parent-task")
    assert parent_span.context is not None

    child_span = find_span_by_run_name(*spans, run_name="child-flow")
    assert child_span.context is not None

    grandchild_span = find_span_by_run_name(*spans, run_name="grandchild-task")
    assert grandchild_span.context is not None

    assert parent_span.parent is None
    assert (
        parent_span.context.trace_id
        == child_span.context.trace_id
        == grandchild_span.context.trace_id
    )

    # The child span should have the `parent_span` as its parent
    assert child_span.parent is not None
    assert child_span.parent.span_id == parent_span.context.span_id

    # The grandchild span should have the `child_span` as its parent
    assert grandchild_span.parent is not None
    assert grandchild_span.parent.span_id == child_span.context.span_id


async def test_nested_task_flow_flow(
    engine_type: Literal["async", "sync"],
    instrumentation: InstrumentationTester,
):
    @task(task_run_name="parent-task")
    async def async_parent_task():
        await async_child_flow()

    @task(task_run_name="parent-task")
    def sync_parent_task():
        sync_child_flow()

    @flow(flow_run_name="child-flow")
    def sync_child_flow():
        sync_grandchild_flow()

    @flow(flow_run_name="child-flow")
    async def async_child_flow():
        await async_grandchild_flow()

    @flow(flow_run_name="grandchild-flow")
    def sync_grandchild_flow():
        pass

    @flow(flow_run_name="grandchild-flow")
    async def async_grandchild_flow():
        pass

    the_task = async_parent_task if engine_type == "async" else sync_parent_task
    await run_task(
        the_task, task_run_id=uuid4(), parameters={}, engine_type=engine_type
    )

    spans = instrumentation.get_finished_spans()
    assert len(spans) == 3

    parent_span = find_span_by_run_name(*spans, run_name="parent-task")
    assert parent_span.context is not None
    child_span = find_span_by_run_name(*spans, run_name="child-flow")
    assert child_span.context is not None
    grandchild_span = find_span_by_run_name(*spans, run_name="grandchild-flow")
    assert grandchild_span.context is not None

    assert parent_span.parent is None
    assert (
        parent_span.context.trace_id
        == child_span.context.trace_id
        == grandchild_span.context.trace_id
    )
    # The child span should have the `parent_span` as its parent
    assert child_span.parent is not None
    assert child_span.parent.span_id == parent_span.context.span_id
    # The grandchild span should have the `child_span` as its parent
    assert grandchild_span.parent is not None
    assert grandchild_span.parent.span_id == child_span.context.span_id


async def test_nested_flow_flow_task(
    engine_type: Literal["async", "sync"],
    instrumentation: InstrumentationTester,
    sync_prefect_client: SyncPrefectClient,
):
    @flow(flow_run_name="parent-flow")
    async def async_parent_flow():
        await async_child_flow()

    @flow(flow_run_name="parent-flow")
    def sync_parent_flow():
        sync_child_flow()

    @flow(flow_run_name="child-flow")
    async def async_child_flow():
        await async_grandchild_task()

    @flow(flow_run_name="child-flow")
    def sync_child_flow():
        sync_grandchild_task()

    @task(task_run_name="grandchild-task")
    async def async_grandchild_task():
        pass

    @task(task_run_name="grandchild-task")
    def sync_grandchild_task():
        pass

    the_flow = async_parent_flow if engine_type == "async" else sync_parent_flow
    flow_run = sync_prefect_client.create_flow_run(the_flow)  # type: ignore

    await run_flow(the_flow, flow_run=flow_run, engine_type=engine_type)

    spans = instrumentation.get_finished_spans()
    assert len(spans) == 3

    parent_span = find_span_by_run_name(*spans, run_name="parent-flow")
    assert parent_span.context is not None

    child_span = find_span_by_run_name(*spans, run_name="child-flow")
    assert child_span.context is not None

    grandchild_span = find_span_by_run_name(*spans, run_name="grandchild-task")
    assert grandchild_span.context is not None

    assert parent_span.parent is None
    assert (
        parent_span.context.trace_id
        == child_span.context.trace_id
        == grandchild_span.context.trace_id
    )

    # The child span should have the `parent_span` as its parent
    assert child_span.parent is not None
    assert child_span.parent.span_id == parent_span.context.span_id

    # The grandchild span should have the `child_span` as its parent
    assert grandchild_span.parent is not None
    assert grandchild_span.parent.span_id == child_span.context.span_id


async def test_nested_flow_flow_flow(
    engine_type: Literal["async", "sync"],
    instrumentation: InstrumentationTester,
    sync_prefect_client: SyncPrefectClient,
):
    @flow(flow_run_name="parent-flow")
    async def async_parent_flow():
        await async_child_flow()

    @flow(flow_run_name="parent-flow")
    def sync_parent_flow():
        sync_child_flow()

    @flow(flow_run_name="child-flow")
    async def async_child_flow():
        await async_grandchild_flow()

    @flow(flow_run_name="child-flow")
    def sync_child_flow():
        sync_grandchild_flow()

    @flow(flow_run_name="grandchild-flow")
    async def async_grandchild_flow():
        pass

    @flow(flow_run_name="grandchild-flow")
    def sync_grandchild_flow():
        pass

    the_flow = async_parent_flow if engine_type == "async" else sync_parent_flow
    flow_run = sync_prefect_client.create_flow_run(the_flow)  # type: ignore

    await run_flow(the_flow, flow_run=flow_run, engine_type=engine_type)

    spans = instrumentation.get_finished_spans()
    assert len(spans) == 3

    parent_span = find_span_by_run_name(*spans, run_name="parent-flow")
    assert parent_span.context is not None

    child_span = find_span_by_run_name(*spans, run_name="child-flow")
    assert child_span.context is not None

    grandchild_span = find_span_by_run_name(*spans, run_name="grandchild-flow")
    assert grandchild_span.context is not None

    assert parent_span.parent is None
    assert (
        parent_span.context.trace_id
        == child_span.context.trace_id
        == grandchild_span.context.trace_id
    )

    # The child span should have the `parent_span` as its parent
    assert child_span.parent is not None
    assert child_span.parent.span_id == parent_span.context.span_id

    # The grandchild span should have the `child_span` as its parent
    assert grandchild_span.parent is not None
    assert grandchild_span.parent.span_id == child_span.context.span_id


async def test_nested_task_task_task(
    engine_type: Literal["async", "sync"],
    instrumentation: InstrumentationTester,
):
    @task(task_run_name="parent-task")
    async def async_parent_task():
        await async_child_task()

    @task(task_run_name="parent-task")
    def sync_parent_task():
        sync_child_task()

    @task(task_run_name="child-task")
    async def async_child_task():
        await async_grandchild_task()

    @task(task_run_name="child-task")
    def sync_child_task():
        sync_grandchild_task()

    @task(task_run_name="grandchild-task")
    async def async_grandchild_task():
        pass

    @task(task_run_name="grandchild-task")
    def sync_grandchild_task():
        pass

    the_task = async_parent_task if engine_type == "async" else sync_parent_task
    await run_task(
        the_task, task_run_id=uuid4(), parameters={}, engine_type=engine_type
    )

    spans = instrumentation.get_finished_spans()
    assert len(spans) == 3

    parent_span = find_span_by_run_name(*spans, run_name="parent-task")
    assert parent_span.context is not None

    child_span = find_span_by_run_name(*spans, run_name="child-task")
    assert child_span.context is not None

    grandchild_span = find_span_by_run_name(*spans, run_name="grandchild-task")
    assert grandchild_span.context is not None

    assert parent_span.parent is None
    assert (
        parent_span.context.trace_id
        == child_span.context.trace_id
        == grandchild_span.context.trace_id
    )

    # The child span should have the `parent_span` as its parent
    assert child_span.parent is not None
    assert child_span.parent.span_id == parent_span.context.span_id

    # The grandchild span should have the `child_span` as its parent
    assert grandchild_span.parent is not None
    assert grandchild_span.parent.span_id == child_span.context.span_id


async def test_nested_task_task_flow(
    engine_type: Literal["async", "sync"],
    instrumentation: InstrumentationTester,
):
    @task(task_run_name="parent-task")
    async def async_parent_task():
        await async_child_task()

    @task(task_run_name="parent-task")
    def sync_parent_task():
        sync_child_task()

    @task(task_run_name="child-task")
    async def async_child_task():
        await async_grandchild_flow()

    @task(task_run_name="child-task")
    def sync_child_task():
        sync_grandchild_flow()

    @flow(flow_run_name="grandchild-flow")
    async def async_grandchild_flow():
        pass

    @flow(flow_run_name="grandchild-flow")
    def sync_grandchild_flow():
        pass

    the_task = async_parent_task if engine_type == "async" else sync_parent_task
    await run_task(
        the_task, task_run_id=uuid4(), parameters={}, engine_type=engine_type
    )

    spans = instrumentation.get_finished_spans()
    assert len(spans) == 3

    parent_span = find_span_by_run_name(*spans, run_name="parent-task")
    assert parent_span.context is not None

    child_span = find_span_by_run_name(*spans, run_name="child-task")
    assert child_span.context is not None

    grandchild_span = find_span_by_run_name(*spans, run_name="grandchild-flow")
    assert grandchild_span.context is not None

    assert parent_span.parent is None
    assert (
        parent_span.context.trace_id
        == child_span.context.trace_id
        == grandchild_span.context.trace_id
    )

    # The child span should have the `parent_span` as its parent
    assert child_span.parent is not None
    assert child_span.parent.span_id == parent_span.context.span_id

    # The grandchild span should have the `child_span` as its parent
    assert grandchild_span.parent is not None
    assert grandchild_span.parent.span_id == child_span.context.span_id


async def test_span_name_with_string_template(
    engine_type: Literal["async", "sync"],
    instrumentation: InstrumentationTester,
):
    """Test that spans use the formatted name when string templates are used"""
    test_value = "template-test"

    @task(task_run_name=f"task-{test_value}")
    async def async_task(value: str):
        return value

    @task(task_run_name=f"task-{test_value}")
    def sync_task(value: str):
        return value

    task_fn = async_task if engine_type == "async" else sync_task
    task_run_id = uuid4()

    await run_task(
        task_fn,
        task_run_id=task_run_id,
        parameters={"value": test_value},
        engine_type=engine_type,
    )

    spans = instrumentation.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    expected_name = f"task-{test_value}"
    assert span.name == expected_name
    assert span.attributes["prefect.run.name"] == expected_name


async def test_no_span_when_telemetry_disabled(
    engine_type: Literal["async", "sync"],
    instrumentation: InstrumentationTester,
):
    """Test that no spans are created when telemetry is disabled"""
    # Disable telemetry
    with temporary_settings({PREFECT_CLOUD_ENABLE_ORCHESTRATION_TELEMETRY: False}):

        @task(task_run_name="test-task")
        async def async_task(x: int, y: int):
            return x + y

        @task(task_run_name="test-task")
        def sync_task(x: int, y: int):
            return x + y

        task_fn = async_task if engine_type == "async" else sync_task
        task_run_id = uuid4()

        await run_task(
            task_fn,
            task_run_id=task_run_id,
            parameters={"x": 1, "y": 2},
            engine_type=engine_type,
        )

        # Verify no spans were created
        spans = instrumentation.get_finished_spans()
        assert len(spans) == 0
