import time
from threading import Event, Lock, Thread
from typing import Optional

from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter


class InFlightSpanProcessor(SpanProcessor):
    def __init__(self, span_exporter: SpanExporter):
        self.span_exporter = span_exporter
        self._in_flight = {}
        self._lock = Lock()
        self._stop_event = Event()
        self._export_thread = Thread(target=self._export_periodically, daemon=True)
        self._export_thread.start()

    def _export_periodically(self) -> None:
        while not self._stop_event.is_set():
            time.sleep(1)
            with self._lock:
                to_export = [
                    self._readable_span(span) for span in self._in_flight.values()
                ]
                if to_export:
                    self.span_exporter.export(to_export)

    def _readable_span(self, span: Span) -> ReadableSpan:
        readable = span._readable_span()
        readable._end_time = time.time_ns()
        readable._attributes = {
            **(readable._attributes or {}),
            "prefect.in-flight": True,
        }
        return readable

    def on_start(self, span: Span, parent_context: Optional[Context] = None) -> None:
        if not span.context or not span.context.trace_flags.sampled:
            return
        with self._lock:
            self._in_flight[span.context.span_id] = span

    def on_end(self, span: ReadableSpan) -> None:
        if not span.context or not span.context.trace_flags.sampled:
            return
        with self._lock:
            del self._in_flight[span.context.span_id]
            self.span_exporter.export((span,))

    def shutdown(self) -> None:
        self._stop_event.set()
        self._export_thread.join()
        self.span_exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True
