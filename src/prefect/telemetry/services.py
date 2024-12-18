from abc import abstractmethod
from typing import Union

from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LogData
from opentelemetry.sdk._logs.export import LogExporter
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter

from prefect._internal.concurrency.services import BatchedQueueService


class BaseQueueingExporter(BatchedQueueService):
    _max_batch_size = 512
    _min_interval = 2.0
    _otlp_exporter: Union[SpanExporter, LogExporter]

    def export(self, batch: list[Union[ReadableSpan, LogData]]) -> None:
        for item in batch:
            self.send(item)

    @abstractmethod
    def _export_batch(self, items: list[Union[ReadableSpan, LogData]]) -> None:
        pass

    async def _handle_batch(self, items: list[Union[ReadableSpan, LogData]]) -> None:
        try:
            self._export_batch(items)
        except Exception as e:
            self._logger.exception(f"Failed to export batch: {e}")
            raise

    def shutdown(self) -> None:
        if self._stopped:
            return

        self.drain()
        self._otlp_exporter.shutdown()


class QueueingSpanExporter(BaseQueueingExporter, SpanExporter):
    _otlp_exporter: OTLPSpanExporter

    def __init__(self, endpoint: str, headers: tuple[tuple[str, str]]):
        super().__init__()
        self._otlp_exporter = OTLPSpanExporter(
            endpoint=endpoint,
            headers=dict(headers),
        )

    def _export_batch(self, items: list[ReadableSpan]) -> None:
        self._otlp_exporter.export(items)


class QueueingLogExporter(BaseQueueingExporter, LogExporter):
    _otlp_exporter: OTLPLogExporter

    def __init__(self, endpoint: str, headers: tuple[tuple[str, str]]):
        super().__init__()
        self._otlp_exporter = OTLPLogExporter(
            endpoint=endpoint,
            headers=dict(headers),
        )

    def _export_batch(self, items: list[LogData]) -> None:
        self._otlp_exporter.export(items)
