from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator, Optional

from prefect.logging.loggers import get_logger

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
    from prefect.flows import Flow

logger: logging.Logger = get_logger("prefect.telemetry.metrics")


def _resolve_metrics_endpoint() -> Optional[str]:
    """Resolve the OTLP metrics endpoint.

    Priority:
    1. OTEL_EXPORTER_OTLP_METRICS_ENDPOINT env var (user override)
    2. Auto-derived from Cloud API URL: {api_url}/telemetry/v1/metrics
    3. None if neither available
    """
    explicit = os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")
    if explicit:
        return explicit

    import prefect.settings

    settings = prefect.settings.get_current_settings()
    api_url = settings.api.url
    if api_url and settings.connected_to_cloud:
        return f"{api_url}/telemetry/v1/metrics"

    return None


@contextmanager
def RunMetrics(
    flow_run: FlowRun,
    flow: Flow,
) -> Generator[None, None, None]:
    """Context manager that collects OS-level resource metrics during flow run execution.

    Starts an OpenTelemetry MeterProvider with SystemMetricsInstrumentor, filtered to
    process CPU and memory metrics. Exports via OTLP HTTP.

    Becomes a no-op if:
    - Resource metrics are disabled in settings
    - No OTLP endpoint is available
    - The opentelemetry-instrumentation-system-metrics package is not installed
    """
    import prefect.settings

    settings = prefect.settings.get_current_settings()

    if not settings.telemetry.enable_resource_metrics:
        yield
        return

    endpoint = _resolve_metrics_endpoint()
    if not endpoint:
        yield
        return

    try:
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.instrumentation.system_metrics import (
            SystemMetricsInstrumentor,
        )
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
    except ImportError:
        logger.debug(
            "opentelemetry instrumentation packages not available, "
            "skipping resource metric collection"
        )
        yield
        return

    resource_attributes: dict[str, str] = {
        "prefect.flow-run.id": str(flow_run.id),
        "prefect.flow.name": flow.name,
    }
    if flow_run.deployment_id:
        resource_attributes["prefect.deployment.id"] = str(flow_run.deployment_id)
    if flow_run.work_pool_name:
        resource_attributes["prefect.work-pool.name"] = flow_run.work_pool_name

    resource = Resource.create(resource_attributes)

    headers: dict[str, str] = {}
    api_key = settings.api.key
    if api_key:
        headers["Authorization"] = f"Bearer {api_key.get_secret_value()}"

    exporter = OTLPMetricExporter(
        endpoint=endpoint,
        headers=headers,
    )
    reader = PeriodicExportingMetricReader(
        exporter,
        export_interval_millis=settings.telemetry.resource_metrics_interval_seconds
        * 1000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])

    instrumentor = SystemMetricsInstrumentor(
        config={
            "process.cpu.utilization": None,
            "process.memory.usage": None,
            "process.memory.virtual": None,
        },
    )
    instrumentor.instrument(meter_provider=meter_provider)

    try:
        yield
    finally:
        try:
            instrumentor.uninstrument()
        except Exception:
            logger.debug("Error uninstrumenting system metrics", exc_info=True)
        try:
            meter_provider.shutdown()
        except Exception:
            logger.debug("Error shutting down meter provider", exc_info=True)
