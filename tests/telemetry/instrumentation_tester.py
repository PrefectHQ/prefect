from typing import Any, Dict, Protocol, Tuple, Union

from opentelemetry import metrics as metrics_api
from opentelemetry import trace as trace_api
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import ReadableSpan, Span, TracerProvider, export
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.test.globals_test import (
    reset_metrics_globals,
    reset_trace_globals,
)
from opentelemetry.util.types import Attributes


def create_tracer_provider(**kwargs) -> Tuple[TracerProvider, InMemorySpanExporter]:
    """Helper to create a configured tracer provider.

    Creates and configures a `TracerProvider` with a
    `SimpleSpanProcessor` and a `InMemorySpanExporter`.
    All the parameters passed are forwarded to the TracerProvider
    constructor.

    Returns:
        A list with the tracer provider in the first element and the
        in-memory span exporter in the second.
    """
    tracer_provider = TracerProvider(**kwargs)
    memory_exporter = InMemorySpanExporter()
    span_processor = export.SimpleSpanProcessor(memory_exporter)
    tracer_provider.add_span_processor(span_processor)

    return tracer_provider, memory_exporter


def create_meter_provider(**kwargs) -> Tuple[MeterProvider, InMemoryMetricReader]:
    """Helper to create a configured meter provider
    Creates a `MeterProvider` and an `InMemoryMetricReader`.
    Returns:
        A tuple with the meter provider in the first element and the
        in-memory metrics exporter in the second
    """
    memory_reader = InMemoryMetricReader()
    metric_readers = kwargs.get("metric_readers", [])
    metric_readers.append(memory_reader)
    kwargs["metric_readers"] = metric_readers
    meter_provider = MeterProvider(**kwargs)
    return meter_provider, memory_reader


class HasAttributesViaProperty(Protocol):
    @property
    def attributes(self) -> Attributes: ...


class HasAttributesViaAttr(Protocol):
    attributes: Attributes


HasAttributes = Union[HasAttributesViaProperty, HasAttributesViaAttr]


class InstrumentationTester:
    tracer_provider: TracerProvider
    memory_exporter: InMemorySpanExporter
    meter_provider: MeterProvider
    memory_metrics_reader: InMemoryMetricReader

    def __init__(self):
        self.tracer_provider, self.memory_exporter = create_tracer_provider()
        # This is done because set_tracer_provider cannot override the
        # current tracer provider.
        reset_trace_globals()
        trace_api.set_tracer_provider(self.tracer_provider)

        self.memory_exporter.clear()
        # This is done because set_meter_provider cannot override the
        # current meter provider.
        reset_metrics_globals()

        self.meter_provider, self.memory_metrics_reader = create_meter_provider()
        metrics_api.set_meter_provider(self.meter_provider)

    def reset(self):
        reset_trace_globals()
        reset_metrics_globals()

    def get_finished_spans(self):
        return self.memory_exporter.get_finished_spans()

    @staticmethod
    def assert_has_attributes(obj: HasAttributes, attributes: Dict[str, Any]):
        assert obj.attributes is not None
        for key, val in attributes.items():
            assert key in obj.attributes, f"Key {key!r} not found in attributes"
            assert obj.attributes[key] == val, f"Value for key {key!r} does not match"

    @staticmethod
    def assert_span_instrumented_for(span: Union[Span, ReadableSpan], module):
        assert span.instrumentation_scope is not None
        assert span.instrumentation_scope.name == module.__name__
        assert span.instrumentation_scope.version == module.__version__
