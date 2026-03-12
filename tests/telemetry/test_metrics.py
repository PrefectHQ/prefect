from __future__ import annotations

import builtins
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from prefect.settings.models.telemetry import TelemetrySettings
from prefect.telemetry._metrics import RunMetrics, _resolve_metrics_endpoint


class TestTelemetrySettings:
    def test_defaults(self):
        settings = TelemetrySettings()
        assert settings.enable_resource_metrics is True
        assert settings.resource_metrics_interval_seconds == 10

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("PREFECT_TELEMETRY_ENABLE_RESOURCE_METRICS", "false")
        monkeypatch.setenv("PREFECT_TELEMETRY_RESOURCE_METRICS_INTERVAL_SECONDS", "30")
        settings = TelemetrySettings()
        assert settings.enable_resource_metrics is False
        assert settings.resource_metrics_interval_seconds == 30


class TestResolveMetricsEndpoint:
    @pytest.fixture(autouse=True)
    def _clean_otel_env(self, monkeypatch):
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    def test_metrics_specific_env_var_takes_priority(self, monkeypatch):
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://custom:4318/v1/metrics"
        )
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://other:4318")
        mock_settings = MagicMock()
        mock_settings.connected_to_cloud = False
        endpoint, is_cloud = _resolve_metrics_endpoint(mock_settings)
        assert endpoint == "http://custom:4318/v1/metrics"
        assert is_cloud is False

    def test_generic_otlp_endpoint_fallback(self, monkeypatch):
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
        mock_settings = MagicMock()
        mock_settings.connected_to_cloud = False
        endpoint, is_cloud = _resolve_metrics_endpoint(mock_settings)
        assert endpoint == "http://collector:4318/v1/metrics"
        assert is_cloud is False

    def test_generic_otlp_endpoint_strips_trailing_slash(self, monkeypatch):
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318/")
        mock_settings = MagicMock()
        mock_settings.connected_to_cloud = False
        endpoint, _ = _resolve_metrics_endpoint(mock_settings)
        assert endpoint == "http://collector:4318/v1/metrics"

    def test_env_var_override_does_not_leak_cloud_auth(self, monkeypatch):
        """When endpoint is overridden via env var, is_cloud must be False
        even if connected to Cloud, to avoid leaking the API key to
        third-party collectors."""
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
            "http://my-collector:4318/v1/metrics",
        )
        mock_settings = MagicMock()
        mock_settings.connected_to_cloud = True
        endpoint, is_cloud = _resolve_metrics_endpoint(mock_settings)
        assert endpoint == "http://my-collector:4318/v1/metrics"
        assert is_cloud is False

    def test_generic_env_var_override_does_not_leak_cloud_auth(self, monkeypatch):
        """Same protection for the generic OTEL_EXPORTER_OTLP_ENDPOINT."""
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://my-collector:4318")
        mock_settings = MagicMock()
        mock_settings.connected_to_cloud = True
        endpoint, is_cloud = _resolve_metrics_endpoint(mock_settings)
        assert endpoint == "http://my-collector:4318/v1/metrics"
        assert is_cloud is False

    def test_derives_from_cloud_api_url_strips_trailing_slash(self):
        mock_settings = MagicMock()
        mock_settings.api.url = (
            "https://api.prefect.cloud/api/accounts/abc/workspaces/def/"
        )
        mock_settings.connected_to_cloud = True
        endpoint, _ = _resolve_metrics_endpoint(mock_settings)
        assert (
            endpoint
            == "https://api.prefect.cloud/api/accounts/abc/workspaces/def/telemetry/v1/metrics"
        )

    def test_derives_from_cloud_api_url(self):
        mock_settings = MagicMock()
        mock_settings.api.url = (
            "https://api.prefect.cloud/api/accounts/abc/workspaces/def"
        )
        mock_settings.connected_to_cloud = True
        endpoint, is_cloud = _resolve_metrics_endpoint(mock_settings)
        assert (
            endpoint
            == "https://api.prefect.cloud/api/accounts/abc/workspaces/def/telemetry/v1/metrics"
        )
        assert is_cloud is True

    def test_returns_none_when_not_connected_to_cloud(self):
        mock_settings = MagicMock()
        mock_settings.api.url = "http://localhost:4200/api"
        mock_settings.connected_to_cloud = False
        endpoint, _ = _resolve_metrics_endpoint(mock_settings)
        assert endpoint is None

    def test_returns_none_when_no_api_url(self):
        mock_settings = MagicMock()
        mock_settings.api.url = None
        mock_settings.connected_to_cloud = False
        endpoint, _ = _resolve_metrics_endpoint(mock_settings)
        assert endpoint is None


class TestRunMetrics:
    @pytest.fixture
    def flow_run(self) -> MagicMock:
        run = MagicMock()
        run.id = uuid4()
        run.deployment_id = uuid4()
        run.work_pool_name = "my-pool"
        return run

    @pytest.fixture
    def flow(self) -> MagicMock:
        f = MagicMock()
        f.name = "my-flow"
        return f

    def test_noop_when_disabled(self, flow_run: MagicMock, flow: MagicMock):
        mock_settings = MagicMock()
        mock_settings.telemetry.enable_resource_metrics = False
        with patch("prefect.settings.get_current_settings", return_value=mock_settings):
            with RunMetrics(flow_run, flow):
                pass

    def test_noop_when_no_endpoint(self, flow_run: MagicMock, flow: MagicMock):
        mock_settings = MagicMock()
        mock_settings.telemetry.enable_resource_metrics = True
        with (
            patch("prefect.settings.get_current_settings", return_value=mock_settings),
            patch(
                "prefect.telemetry._metrics._resolve_metrics_endpoint",
                return_value=(None, False),
            ),
        ):
            with RunMetrics(flow_run, flow):
                pass

    def test_noop_when_import_fails(self, flow_run: MagicMock, flow: MagicMock):
        mock_settings = MagicMock()
        mock_settings.telemetry.enable_resource_metrics = True
        original_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if "system_metrics" in name or "otlp" in name:
                raise ImportError("not installed")
            return original_import(name, *args, **kwargs)

        with (
            patch("prefect.settings.get_current_settings", return_value=mock_settings),
            patch(
                "prefect.telemetry._metrics._resolve_metrics_endpoint",
                return_value=("http://localhost:4318/v1/metrics", False),
            ),
            patch.object(builtins, "__import__", side_effect=mock_import),
        ):
            with RunMetrics(flow_run, flow):
                pass

    def test_instruments_and_shuts_down(self, flow_run: MagicMock, flow: MagicMock):
        mock_settings = MagicMock()
        mock_settings.telemetry.enable_resource_metrics = True
        mock_settings.telemetry.resource_metrics_interval_seconds = 10

        mock_instrumentor = MagicMock()
        mock_meter_provider = MagicMock()
        mock_resource = MagicMock()

        with (
            patch("prefect.settings.get_current_settings", return_value=mock_settings),
            patch(
                "prefect.telemetry._metrics._resolve_metrics_endpoint",
                return_value=("http://localhost:4318/v1/metrics", False),
            ),
            patch(
                "opentelemetry.instrumentation.system_metrics.SystemMetricsInstrumentor",
                return_value=mock_instrumentor,
            ),
            patch(
                "opentelemetry.sdk.metrics.MeterProvider",
                return_value=mock_meter_provider,
            ),
            patch(
                "opentelemetry.exporter.otlp.proto.http.metric_exporter.OTLPMetricExporter"
            ),
            patch("opentelemetry.sdk.metrics.export.PeriodicExportingMetricReader"),
            patch(
                "opentelemetry.sdk.resources.Resource.create",
                return_value=mock_resource,
            ),
        ):
            with RunMetrics(flow_run, flow):
                mock_instrumentor.instrument.assert_called_once_with(
                    meter_provider=mock_meter_provider
                )

            mock_instrumentor.uninstrument.assert_called_once()
            mock_meter_provider.shutdown.assert_called_once()

    def test_noop_when_setup_raises(self, flow_run: MagicMock, flow: MagicMock):
        """Setup errors (e.g. malformed URL, incompatible OTel version) should
        degrade to a no-op, not abort the flow run."""
        mock_settings = MagicMock()
        mock_settings.telemetry.enable_resource_metrics = True
        mock_settings.telemetry.resource_metrics_interval_seconds = 10

        with (
            patch("prefect.settings.get_current_settings", return_value=mock_settings),
            patch(
                "prefect.telemetry._metrics._resolve_metrics_endpoint",
                return_value=("http://localhost:4318/v1/metrics", False),
            ),
            patch(
                "opentelemetry.exporter.otlp.proto.http.metric_exporter.OTLPMetricExporter",
                side_effect=Exception("bad endpoint"),
            ),
            patch(
                "opentelemetry.instrumentation.system_metrics.SystemMetricsInstrumentor",
            ),
            patch("opentelemetry.sdk.metrics.MeterProvider"),
            patch("opentelemetry.sdk.metrics.export.PeriodicExportingMetricReader"),
            patch("opentelemetry.sdk.resources.Resource.create"),
        ):
            # Should not raise — flow body must still execute
            executed = False
            with RunMetrics(flow_run, flow):
                executed = True
            assert executed

    def test_non_cloud_endpoint_preserves_otel_env_headers(
        self, flow_run: MagicMock, flow: MagicMock
    ):
        """Non-cloud endpoints should not pass headers kwarg so that
        OTEL_EXPORTER_OTLP_HEADERS env vars are respected by the exporter."""
        mock_settings = MagicMock()
        mock_settings.telemetry.enable_resource_metrics = True
        mock_settings.telemetry.resource_metrics_interval_seconds = 10

        mock_exporter_cls = MagicMock()

        with (
            patch("prefect.settings.get_current_settings", return_value=mock_settings),
            patch(
                "prefect.telemetry._metrics._resolve_metrics_endpoint",
                return_value=("http://custom-collector:4318/v1/metrics", False),
            ),
            patch(
                "opentelemetry.exporter.otlp.proto.http.metric_exporter.OTLPMetricExporter",
                mock_exporter_cls,
            ),
            patch(
                "opentelemetry.instrumentation.system_metrics.SystemMetricsInstrumentor",
            ),
            patch("opentelemetry.sdk.metrics.MeterProvider"),
            patch("opentelemetry.sdk.metrics.export.PeriodicExportingMetricReader"),
            patch("opentelemetry.sdk.resources.Resource.create"),
        ):
            with RunMetrics(flow_run, flow):
                pass

            call_kwargs = mock_exporter_cls.call_args[1]
            assert "headers" not in call_kwargs

    def test_cloud_endpoint_sends_auth_header(
        self, flow_run: MagicMock, flow: MagicMock
    ):
        """Cloud endpoints should include the Authorization header."""
        mock_settings = MagicMock()
        mock_settings.telemetry.enable_resource_metrics = True
        mock_settings.telemetry.resource_metrics_interval_seconds = 10
        mock_settings.api.key.get_secret_value.return_value = "test-api-key"

        mock_exporter_cls = MagicMock()

        with (
            patch("prefect.settings.get_current_settings", return_value=mock_settings),
            patch(
                "prefect.telemetry._metrics._resolve_metrics_endpoint",
                return_value=("https://cloud.example.com/v1/metrics", True),
            ),
            patch(
                "opentelemetry.exporter.otlp.proto.http.metric_exporter.OTLPMetricExporter",
                mock_exporter_cls,
            ),
            patch(
                "opentelemetry.instrumentation.system_metrics.SystemMetricsInstrumentor",
            ),
            patch("opentelemetry.sdk.metrics.MeterProvider"),
            patch("opentelemetry.sdk.metrics.export.PeriodicExportingMetricReader"),
            patch("opentelemetry.sdk.resources.Resource.create"),
        ):
            with RunMetrics(flow_run, flow):
                pass

            call_kwargs = mock_exporter_cls.call_args[1]
            assert call_kwargs["headers"] == {"Authorization": "Bearer test-api-key"}


class TestEngineIntegration:
    def test_engine_imports_run_metrics(self):
        """Verify engine.py references RunMetrics."""
        import inspect

        import prefect.engine

        source = inspect.getsource(prefect.engine)
        assert "RunMetrics" in source
        assert "from prefect.telemetry._metrics import RunMetrics" in source
