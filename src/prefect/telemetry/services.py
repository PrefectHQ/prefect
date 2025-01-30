from collections.abc import Sequence
from typing import Any, Protocol, TypeVar

from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LogData
from opentelemetry.sdk._logs.export import LogExporter
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from prefect._internal.concurrency.services import BatchedQueueService

BatchItem = TypeVar("BatchItem", ReadableSpan, LogData)
T_contra = TypeVar("T_contra", contravariant=True)


class OTLPExporter(Protocol[T_contra]):
    def export(self, __items: Sequence[T_contra]) -> Any: ...

    def shutdown(self) -> Any: ...


class BaseQueueingExporter(BatchedQueueService[BatchItem]):
    _max_batch_size = 512
    _min_interval = 2.0

    def __init__(self, otlp_exporter: OTLPExporter[BatchItem]) -> None:
        super().__init__()
        self._otlp_exporter = otlp_exporter

    async def _handle_batch(self, items: list[BatchItem]) -> None:
        try:
            self._otlp_exporter.export(items)
        except Exception as e:
            self._logger.exception(f"Failed to export batch: {e}")
            raise

    def shutdown(self) -> None:
        if self._stopped:
            return

        self.drain()
        self._otlp_exporter.shutdown()


class QueueingSpanExporter(BaseQueueingExporter[ReadableSpan], SpanExporter):
    _otlp_exporter: OTLPSpanExporter

    def __init__(self, endpoint: str, headers: tuple[tuple[str, str]]):
        super().__init__(OTLPSpanExporter(endpoint=endpoint, headers=dict(headers)))

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for item in spans:
            if self._stopped:
                break
            self.send(item)
        return SpanExportResult.SUCCESS


class QueueingLogExporter(BaseQueueingExporter[LogData], LogExporter):
    _otlp_exporter: OTLPLogExporter

    def __init__(self, endpoint: str, headers: tuple[tuple[str, str]]) -> None:
        super().__init__(OTLPLogExporter(endpoint=endpoint, headers=dict(headers)))

    def export(self, batch: Sequence[LogData]) -> None:
        for item in batch:
            if self._stopped:
                break
            self.send(item)
