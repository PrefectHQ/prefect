from unittest.mock import Mock, patch

import pytest
from opentelemetry.sdk.trace import ReadableSpan, Span
from opentelemetry.trace import SpanContext, TraceFlags

from prefect.telemetry.processors import InFlightSpanProcessor


@pytest.fixture
def mock_span_exporter():
    return Mock()


@pytest.fixture
def mock_span():
    span = Mock(spec=Span)
    span.context = Mock(
        spec=SpanContext, span_id=123, trace_flags=TraceFlags(TraceFlags.SAMPLED)
    )
    mock_readable = Mock(spec=ReadableSpan)
    mock_readable._attributes = {}
    span._readable_span.return_value = mock_readable
    return span


@pytest.fixture
def processor(mock_span_exporter: Mock):
    return InFlightSpanProcessor(mock_span_exporter)


class TestInFlightSpanProcessor:
    def test_initialization(
        self, processor: InFlightSpanProcessor, mock_span_exporter: Mock
    ):
        assert processor.span_exporter == mock_span_exporter
        assert processor._in_flight == {}
        assert not processor._stop_event.is_set()
        assert processor._export_thread.daemon
        assert processor._export_thread.is_alive()

    def test_span_processing_lifecycle(
        self,
        processor: InFlightSpanProcessor,
        mock_span: Mock,
    ):
        processor.on_start(mock_span)
        assert mock_span.context.span_id in processor._in_flight
        assert processor._in_flight[mock_span.context.span_id] == mock_span

        readable_span = Mock(spec=ReadableSpan)
        readable_span.context = mock_span.context
        processor.on_end(readable_span)

        assert mock_span.context.span_id not in processor._in_flight
        processor.span_exporter.export.assert_called_once_with((readable_span,))

    def test_unsampled_span_ignored(self, processor: InFlightSpanProcessor):
        unsampled_span = Mock(spec=Span)
        unsampled_span.context = Mock(
            spec=SpanContext, trace_flags=TraceFlags(TraceFlags.DEFAULT)
        )

        processor.on_start(unsampled_span)
        assert len(processor._in_flight) == 0

        processor.on_end(unsampled_span)
        processor.span_exporter.export.assert_not_called()

    def test_periodic_export(self, mock_span_exporter: Mock, mock_span: Mock):
        with patch("time.sleep"):
            processor = InFlightSpanProcessor(mock_span_exporter)
            processor.on_start(mock_span)

            with processor._lock:
                to_export = [
                    processor._readable_span(span)
                    for span in processor._in_flight.values()
                ]
                if to_export:
                    processor.span_exporter.export(to_export)

            assert mock_span_exporter.export.called
            exported_spans = mock_span_exporter.export.call_args[0][0]
            assert len(exported_spans) == 1
            assert exported_spans[0]._attributes["prefect.in-flight"] is True

            processor.shutdown()

    def test_concurrent_spans(self, processor: InFlightSpanProcessor):
        spans = [
            Mock(
                spec=Span,
                context=Mock(
                    spec=SpanContext,
                    span_id=i,
                    trace_flags=TraceFlags(TraceFlags.SAMPLED),
                ),
            )
            for i in range(3)
        ]

        for span in spans:
            processor.on_start(span)

        assert len(processor._in_flight) == 3

        for span in reversed(spans):
            readable_span = Mock(spec=ReadableSpan)
            readable_span.context = span.context
            processor.on_end(readable_span)

        assert len(processor._in_flight) == 0

    def test_shutdown(self, processor: InFlightSpanProcessor):
        processor.shutdown()

        assert processor._stop_event.is_set()
        assert not processor._export_thread.is_alive()
        processor.span_exporter.shutdown.assert_called_once()

    def test_span_without_context(self, processor: InFlightSpanProcessor):
        span_without_context = Mock(spec=Span)
        span_without_context.context = None

        processor.on_start(span_without_context)
        assert len(processor._in_flight) == 0

        processor.on_end(span_without_context)
        processor.span_exporter.export.assert_not_called()

    def test_readable_span_attributes(
        self, processor: InFlightSpanProcessor, mock_span: Mock
    ):
        readable = processor._readable_span(mock_span)

        assert readable._attributes
        assert "prefect.in-flight" in readable._attributes
        assert readable._attributes["prefect.in-flight"] is True
        assert isinstance(readable._end_time, int)

    def test_force_flush(self, processor: InFlightSpanProcessor):
        assert processor.force_flush() is True
        assert processor.force_flush(timeout_millis=100) is True
