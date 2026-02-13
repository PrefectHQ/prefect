"""Unit tests for the source freshness module."""

from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from conftest import (
    _make_node,
    _make_source_node,
    write_manifest,
    write_sources_json,
)
from dbt.artifacts.resources.types import NodeType
from prefect_dbt.core._freshness import (
    SourceFreshnessResult,
    _period_to_timedelta,
    compute_freshness_expiration,
    filter_stale_nodes,
    get_source_ancestors,
    parse_source_freshness_results,
    run_source_freshness,
)
from prefect_dbt.core._manifest import DbtNode


class TestPeriodToTimedelta:
    def test_minute(self):
        assert _period_to_timedelta(5, "minute") == timedelta(minutes=5)

    def test_hour(self):
        assert _period_to_timedelta(12, "hour") == timedelta(hours=12)

    def test_day(self):
        assert _period_to_timedelta(3, "day") == timedelta(days=3)

    def test_unknown_period_raises(self):
        with pytest.raises(ValueError, match="Unrecognized freshness period"):
            _period_to_timedelta(1, "week")

    def test_zero_count(self):
        assert _period_to_timedelta(0, "hour") == timedelta(0)


class TestParseSourceFreshnessResults:
    def test_basic_pass(self, tmp_path):
        path = write_sources_json(
            tmp_path,
            [
                {
                    "unique_id": "source.proj.raw.users",
                    "status": "pass",
                    "max_loaded_at": "2024-01-15T10:00:00Z",
                    "snapshotted_at": "2024-01-15T12:00:00Z",
                    "max_loaded_at_time_ago_in_s": 7200.0,
                    "criteria": {
                        "warn_after": {"count": 12, "period": "hour"},
                        "error_after": {"count": 24, "period": "hour"},
                    },
                }
            ],
        )
        results = parse_source_freshness_results(path)
        assert len(results) == 1

        r = results["source.proj.raw.users"]
        assert r.status == "pass"
        assert r.max_loaded_at_time_ago_in_s == 7200.0
        assert r.warn_after == timedelta(hours=12)
        assert r.error_after == timedelta(hours=24)
        assert r.max_loaded_at is not None
        assert r.snapshotted_at is not None

    def test_error_status(self, tmp_path):
        path = write_sources_json(
            tmp_path,
            [
                {
                    "unique_id": "source.proj.raw.events",
                    "status": "error",
                    "max_loaded_at": "2024-01-01T00:00:00Z",
                    "snapshotted_at": "2024-01-15T12:00:00Z",
                    "max_loaded_at_time_ago_in_s": 1252800.0,
                    "criteria": {
                        "warn_after": {"count": 1, "period": "day"},
                        "error_after": {"count": 2, "period": "day"},
                    },
                }
            ],
        )
        results = parse_source_freshness_results(path)
        assert results["source.proj.raw.events"].status == "error"

    def test_multiple_sources(self, tmp_path):
        path = write_sources_json(
            tmp_path,
            [
                {
                    "unique_id": "source.proj.raw.a",
                    "status": "pass",
                    "max_loaded_at_time_ago_in_s": 100.0,
                    "criteria": {},
                },
                {
                    "unique_id": "source.proj.raw.b",
                    "status": "warn",
                    "max_loaded_at_time_ago_in_s": 200.0,
                    "criteria": {},
                },
            ],
        )
        results = parse_source_freshness_results(path)
        assert len(results) == 2
        assert "source.proj.raw.a" in results
        assert "source.proj.raw.b" in results

    def test_no_criteria(self, tmp_path):
        path = write_sources_json(
            tmp_path,
            [
                {
                    "unique_id": "source.proj.raw.x",
                    "status": "pass",
                    "max_loaded_at_time_ago_in_s": 50.0,
                    "criteria": {},
                }
            ],
        )
        results = parse_source_freshness_results(path)
        r = results["source.proj.raw.x"]
        assert r.warn_after is None
        assert r.error_after is None

    def test_empty_results(self, tmp_path):
        path = write_sources_json(tmp_path, [])
        results = parse_source_freshness_results(path)
        assert results == {}

    def test_runtime_error_status(self, tmp_path):
        path = write_sources_json(
            tmp_path,
            [
                {
                    "unique_id": "source.proj.raw.broken",
                    "status": "runtime error",
                    "criteria": {},
                }
            ],
        )
        results = parse_source_freshness_results(path)
        assert results["source.proj.raw.broken"].status == "runtime error"

    def test_missing_timestamps_handled(self, tmp_path):
        path = write_sources_json(
            tmp_path,
            [
                {
                    "unique_id": "source.proj.raw.no_ts",
                    "status": "pass",
                    "criteria": {},
                }
            ],
        )
        results = parse_source_freshness_results(path)
        r = results["source.proj.raw.no_ts"]
        assert r.max_loaded_at is None
        assert r.snapshotted_at is None
        assert r.max_loaded_at_time_ago_in_s is None


class TestGetSourceAncestors:
    def _build_all_nodes(self) -> dict[str, DbtNode]:
        """Build a simple graph: source -> staging -> mart."""
        return {
            "source.test.raw.customers": _make_source_node(
                unique_id="source.test.raw.customers",
                name="customers",
            ),
            "source.test.raw.orders": _make_source_node(
                unique_id="source.test.raw.orders",
                name="orders",
            ),
            "model.test.stg_customers": _make_node(
                unique_id="model.test.stg_customers",
                name="stg_customers",
                depends_on=("source.test.raw.customers",),
                materialization="view",
            ),
            "model.test.stg_orders": _make_node(
                unique_id="model.test.stg_orders",
                name="stg_orders",
                depends_on=("source.test.raw.orders",),
                materialization="view",
            ),
            "model.test.mart": _make_node(
                unique_id="model.test.mart",
                name="mart",
                depends_on=(
                    "model.test.stg_customers",
                    "model.test.stg_orders",
                ),
                materialization="table",
            ),
        }

    def test_direct_source_dependency(self):
        all_nodes = self._build_all_nodes()
        ancestors = get_source_ancestors("model.test.stg_customers", all_nodes)
        assert ancestors == {"source.test.raw.customers"}

    def test_transitive_source_through_models(self):
        all_nodes = self._build_all_nodes()
        ancestors = get_source_ancestors("model.test.mart", all_nodes)
        assert ancestors == {
            "source.test.raw.customers",
            "source.test.raw.orders",
        }

    def test_no_sources(self):
        all_nodes = {
            "model.test.a": _make_node(
                unique_id="model.test.a", name="a", depends_on=()
            ),
            "model.test.b": _make_node(
                unique_id="model.test.b",
                name="b",
                depends_on=("model.test.a",),
            ),
        }
        ancestors = get_source_ancestors("model.test.b", all_nodes)
        assert ancestors == set()

    def test_ephemeral_chain(self):
        """Source -> ephemeral -> model should trace through ephemeral."""
        all_nodes = {
            "source.test.raw.data": _make_source_node(
                unique_id="source.test.raw.data",
                name="data",
            ),
            "model.test.ephemeral_step": DbtNode(
                unique_id="model.test.ephemeral_step",
                name="ephemeral_step",
                resource_type=NodeType.Model,
                depends_on=("source.test.raw.data",),
                materialization="ephemeral",
            ),
            "model.test.final": _make_node(
                unique_id="model.test.final",
                name="final",
                depends_on=("model.test.ephemeral_step",),
                materialization="table",
            ),
        }
        ancestors = get_source_ancestors("model.test.final", all_nodes)
        assert ancestors == {"source.test.raw.data"}

    def test_diamond_graph(self):
        """Diamond: source -> A, B -> C. C should find the single source."""
        all_nodes = {
            "source.test.raw.s": _make_source_node(
                unique_id="source.test.raw.s", name="s"
            ),
            "model.test.a": _make_node(
                unique_id="model.test.a",
                name="a",
                depends_on=("source.test.raw.s",),
            ),
            "model.test.b": _make_node(
                unique_id="model.test.b",
                name="b",
                depends_on=("source.test.raw.s",),
            ),
            "model.test.c": _make_node(
                unique_id="model.test.c",
                name="c",
                depends_on=("model.test.a", "model.test.b"),
            ),
        }
        ancestors = get_source_ancestors("model.test.c", all_nodes)
        assert ancestors == {"source.test.raw.s"}

    def test_unknown_node(self):
        ancestors = get_source_ancestors("model.test.nonexistent", {})
        assert ancestors == set()


class TestComputeFreshnessExpiration:
    def _build_graph_and_results(
        self, time_ago_seconds: float, warn_hours: int = 12
    ) -> tuple[dict[str, DbtNode], dict[str, SourceFreshnessResult]]:
        all_nodes = {
            "source.test.raw.s": _make_source_node(
                unique_id="source.test.raw.s", name="s"
            ),
            "model.test.m": _make_node(
                unique_id="model.test.m",
                name="m",
                depends_on=("source.test.raw.s",),
            ),
        }
        freshness_results = {
            "source.test.raw.s": SourceFreshnessResult(
                unique_id="source.test.raw.s",
                status="pass",
                max_loaded_at_time_ago_in_s=time_ago_seconds,
                warn_after=timedelta(hours=warn_hours),
            ),
        }
        return all_nodes, freshness_results

    def test_within_threshold(self):
        # 2 hours ago, warn at 12 hours -> 10 hours remaining
        all_nodes, results = self._build_graph_and_results(7200.0, 12)
        exp = compute_freshness_expiration("model.test.m", all_nodes, results)
        assert exp == timedelta(hours=12) - timedelta(seconds=7200)

    def test_past_threshold_clamps_to_zero(self):
        # 24 hours ago, warn at 12 hours -> 0 remaining
        all_nodes, results = self._build_graph_and_results(86400.0, 12)
        exp = compute_freshness_expiration("model.test.m", all_nodes, results)
        assert exp == timedelta(0)

    def test_multiple_sources_takes_min(self):
        all_nodes = {
            "source.test.raw.a": _make_source_node(
                unique_id="source.test.raw.a", name="a"
            ),
            "source.test.raw.b": _make_source_node(
                unique_id="source.test.raw.b", name="b"
            ),
            "model.test.m": _make_node(
                unique_id="model.test.m",
                name="m",
                depends_on=("source.test.raw.a", "source.test.raw.b"),
            ),
        }
        freshness_results = {
            "source.test.raw.a": SourceFreshnessResult(
                unique_id="source.test.raw.a",
                status="pass",
                max_loaded_at_time_ago_in_s=3600.0,  # 1 hour ago
                warn_after=timedelta(hours=6),  # 5 hours remaining
            ),
            "source.test.raw.b": SourceFreshnessResult(
                unique_id="source.test.raw.b",
                status="pass",
                max_loaded_at_time_ago_in_s=3600.0,  # 1 hour ago
                warn_after=timedelta(hours=3),  # 2 hours remaining
            ),
        }
        exp = compute_freshness_expiration("model.test.m", all_nodes, freshness_results)
        # Should be min(5h, 2h) = 2h
        assert exp == timedelta(hours=3) - timedelta(seconds=3600)

    def test_no_freshness_data_returns_none(self):
        all_nodes = {
            "source.test.raw.s": _make_source_node(
                unique_id="source.test.raw.s", name="s"
            ),
            "model.test.m": _make_node(
                unique_id="model.test.m",
                name="m",
                depends_on=("source.test.raw.s",),
            ),
        }
        exp = compute_freshness_expiration("model.test.m", all_nodes, {})
        assert exp is None

    def test_no_source_ancestors_returns_none(self):
        all_nodes = {
            "model.test.a": _make_node(
                unique_id="model.test.a", name="a", depends_on=()
            ),
        }
        exp = compute_freshness_expiration("model.test.a", all_nodes, {})
        assert exp is None

    def test_source_without_warn_after_skipped(self):
        all_nodes = {
            "source.test.raw.s": _make_source_node(
                unique_id="source.test.raw.s", name="s"
            ),
            "model.test.m": _make_node(
                unique_id="model.test.m",
                name="m",
                depends_on=("source.test.raw.s",),
            ),
        }
        freshness_results = {
            "source.test.raw.s": SourceFreshnessResult(
                unique_id="source.test.raw.s",
                status="pass",
                max_loaded_at_time_ago_in_s=100.0,
                warn_after=None,  # No threshold
            ),
        }
        exp = compute_freshness_expiration("model.test.m", all_nodes, freshness_results)
        assert exp is None


class TestFilterStaleNodes:
    def _build_graph(self):
        """Source -> stg -> mart, plus an independent model."""
        all_nodes = {
            "source.test.raw.customers": _make_source_node(
                unique_id="source.test.raw.customers", name="customers"
            ),
            "source.test.raw.orders": _make_source_node(
                unique_id="source.test.raw.orders", name="orders"
            ),
            "model.test.stg_customers": _make_node(
                unique_id="model.test.stg_customers",
                name="stg_customers",
                depends_on=("source.test.raw.customers",),
                materialization="view",
            ),
            "model.test.stg_orders": _make_node(
                unique_id="model.test.stg_orders",
                name="stg_orders",
                depends_on=("source.test.raw.orders",),
                materialization="view",
            ),
            "model.test.mart": _make_node(
                unique_id="model.test.mart",
                name="mart",
                depends_on=(
                    "model.test.stg_customers",
                    "model.test.stg_orders",
                ),
                materialization="table",
            ),
            "model.test.independent": _make_node(
                unique_id="model.test.independent",
                name="independent",
                depends_on=(),
                materialization="table",
            ),
        }
        # Executable nodes (no sources)
        nodes = {
            k: v for k, v in all_nodes.items() if v.resource_type != NodeType.Source
        }
        return nodes, all_nodes

    def test_no_stale_sources_returns_all(self):
        nodes, all_nodes = self._build_graph()
        freshness = {
            "source.test.raw.customers": SourceFreshnessResult(
                unique_id="source.test.raw.customers", status="pass"
            ),
            "source.test.raw.orders": SourceFreshnessResult(
                unique_id="source.test.raw.orders", status="pass"
            ),
        }
        remaining, skipped = filter_stale_nodes(nodes, all_nodes, freshness)
        assert remaining == nodes
        assert skipped == {}

    def test_stale_source_removes_dependent(self):
        nodes, all_nodes = self._build_graph()
        freshness = {
            "source.test.raw.customers": SourceFreshnessResult(
                unique_id="source.test.raw.customers", status="error"
            ),
            "source.test.raw.orders": SourceFreshnessResult(
                unique_id="source.test.raw.orders", status="pass"
            ),
        }
        remaining, skipped = filter_stale_nodes(nodes, all_nodes, freshness)

        # stg_customers depends on stale source -> removed
        assert "model.test.stg_customers" not in remaining
        assert "model.test.stg_customers" in skipped
        assert skipped["model.test.stg_customers"]["status"] == "skipped"
        assert "stale source" in skipped["model.test.stg_customers"]["reason"]

        # stg_orders is fine -> kept
        assert "model.test.stg_orders" in remaining

    def test_downstream_cascade(self):
        nodes, all_nodes = self._build_graph()
        freshness = {
            "source.test.raw.customers": SourceFreshnessResult(
                unique_id="source.test.raw.customers", status="error"
            ),
            "source.test.raw.orders": SourceFreshnessResult(
                unique_id="source.test.raw.orders", status="pass"
            ),
        }
        remaining, skipped = filter_stale_nodes(nodes, all_nodes, freshness)

        # mart depends on stg_customers (stale) -> cascaded removal
        assert "model.test.mart" not in remaining
        assert "model.test.mart" in skipped

    def test_independent_nodes_unaffected(self):
        nodes, all_nodes = self._build_graph()
        freshness = {
            "source.test.raw.customers": SourceFreshnessResult(
                unique_id="source.test.raw.customers", status="error"
            ),
            "source.test.raw.orders": SourceFreshnessResult(
                unique_id="source.test.raw.orders", status="error"
            ),
        }
        remaining, skipped = filter_stale_nodes(nodes, all_nodes, freshness)

        # independent has no source dependencies -> still present
        assert "model.test.independent" in remaining
        assert "model.test.independent" not in skipped

    def test_runtime_error_treated_as_stale(self):
        nodes, all_nodes = self._build_graph()
        freshness = {
            "source.test.raw.customers": SourceFreshnessResult(
                unique_id="source.test.raw.customers", status="runtime error"
            ),
            "source.test.raw.orders": SourceFreshnessResult(
                unique_id="source.test.raw.orders", status="pass"
            ),
        }
        remaining, skipped = filter_stale_nodes(nodes, all_nodes, freshness)
        assert "model.test.stg_customers" in skipped

    def test_empty_freshness_results_returns_all(self):
        nodes, all_nodes = self._build_graph()
        remaining, skipped = filter_stale_nodes(nodes, all_nodes, {})
        assert remaining == nodes
        assert skipped == {}

    def test_all_sources_stale(self):
        nodes, all_nodes = self._build_graph()
        freshness = {
            "source.test.raw.customers": SourceFreshnessResult(
                unique_id="source.test.raw.customers", status="error"
            ),
            "source.test.raw.orders": SourceFreshnessResult(
                unique_id="source.test.raw.orders", status="error"
            ),
        }
        remaining, skipped = filter_stale_nodes(nodes, all_nodes, freshness)

        # Only independent should remain
        assert set(remaining.keys()) == {"model.test.independent"}
        # All source-dependent nodes should be skipped
        assert "model.test.stg_customers" in skipped
        assert "model.test.stg_orders" in skipped
        assert "model.test.mart" in skipped


class TestRunSourceFreshness:
    def test_successful_invocation(self, tmp_path):
        """run_source_freshness invokes dbtRunner and parses results."""
        settings = MagicMock()
        settings.project_dir = tmp_path
        settings.target_path = Path("target")

        # Create the sources.json file that dbt would produce
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        write_sources_json(
            target_dir,
            [
                {
                    "unique_id": "source.proj.raw.users",
                    "status": "pass",
                    "max_loaded_at_time_ago_in_s": 100.0,
                    "criteria": {
                        "warn_after": {"count": 12, "period": "hour"},
                    },
                }
            ],
        )

        mock_result = MagicMock()
        mock_result.success = True

        with patch("dbt.cli.main.dbtRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            mock_runner.invoke.return_value = mock_result
            mock_runner_cls.return_value = mock_runner
            settings.resolve_profiles_yml = MagicMock()
            settings.resolve_profiles_yml.return_value.__enter__ = MagicMock(
                return_value="/profiles"
            )
            settings.resolve_profiles_yml.return_value.__exit__ = MagicMock(
                return_value=False
            )

            results = run_source_freshness(settings)

        assert "source.proj.raw.users" in results
        assert results["source.proj.raw.users"].status == "pass"

    def test_graceful_degradation_on_exception(self, tmp_path):
        """Returns empty dict when dbt source freshness raises."""
        settings = MagicMock()
        settings.project_dir = tmp_path
        settings.target_path = Path("target")

        with patch("dbt.cli.main.dbtRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            mock_runner.invoke.side_effect = RuntimeError("dbt crashed")
            mock_runner_cls.return_value = mock_runner
            settings.resolve_profiles_yml = MagicMock()
            settings.resolve_profiles_yml.return_value.__enter__ = MagicMock(
                return_value="/profiles"
            )
            settings.resolve_profiles_yml.return_value.__exit__ = MagicMock(
                return_value=False
            )

            results = run_source_freshness(settings)

        assert results == {}

    def test_graceful_degradation_when_no_output(self, tmp_path):
        """Returns empty dict when sources.json is not produced."""
        settings = MagicMock()
        settings.project_dir = tmp_path
        settings.target_path = Path("target")

        mock_result = MagicMock()
        mock_result.success = False

        with patch("dbt.cli.main.dbtRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            mock_runner.invoke.return_value = mock_result
            mock_runner_cls.return_value = mock_runner
            settings.resolve_profiles_yml = MagicMock()
            settings.resolve_profiles_yml.return_value.__enter__ = MagicMock(
                return_value="/profiles"
            )
            settings.resolve_profiles_yml.return_value.__exit__ = MagicMock(
                return_value=False
            )

            results = run_source_freshness(settings)

        assert results == {}


class TestOrchestratorFreshnessIntegration:
    """Test freshness features via the orchestrator with mocked dbt execution."""

    def _make_freshness_results(self, sources_json_path):
        """Helper to parse freshness results from a sources.json file."""
        return parse_source_freshness_results(sources_json_path)

    def test_only_fresh_sources_skips_stale(self, tmp_path, source_manifest_data):
        """only_fresh_sources=True skips nodes with stale upstream sources."""
        from conftest import _make_mock_executor, _make_mock_settings
        from prefect_dbt.core._orchestrator import (
            ExecutionMode,
            PrefectDbtOrchestrator,
        )

        manifest_path = write_manifest(tmp_path, source_manifest_data)
        settings = _make_mock_settings(project_dir=tmp_path)
        executor = _make_mock_executor(success=True)

        # Write sources.json with one stale source
        target_dir = manifest_path.parent
        write_sources_json(
            target_dir,
            [
                {
                    "unique_id": "source.test.raw.customers",
                    "status": "error",
                    "max_loaded_at_time_ago_in_s": 999999.0,
                    "criteria": {
                        "warn_after": {"count": 1, "period": "day"},
                        "error_after": {"count": 2, "period": "day"},
                    },
                },
                {
                    "unique_id": "source.test.raw.orders",
                    "status": "pass",
                    "max_loaded_at_time_ago_in_s": 100.0,
                    "criteria": {
                        "warn_after": {"count": 1, "period": "day"},
                    },
                },
            ],
        )

        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=manifest_path,
            executor=executor,
            execution_mode=ExecutionMode.PER_WAVE,
        )

        freshness_data = self._make_freshness_results(target_dir / "sources.json")

        with patch(
            "prefect_dbt.core._freshness.run_source_freshness",
            return_value=freshness_data,
        ):
            results = orch.run_build(only_fresh_sources=True)

        # stg_src_customers should be skipped (depends on stale customers source)
        assert results["model.test.stg_src_customers"]["status"] == "skipped"
        assert "stale source" in results["model.test.stg_src_customers"]["reason"]

        # src_customer_summary should be skipped (cascaded from stg_src_customers)
        assert results["model.test.src_customer_summary"]["status"] == "skipped"

        # stg_src_orders should succeed (orders source is fresh)
        assert results["model.test.stg_src_orders"]["status"] == "success"

    def test_use_source_freshness_expiration(self, tmp_path, source_manifest_data):
        """use_source_freshness_expiration computes per-node cache expiration."""
        from conftest import (
            _make_mock_executor_per_node,
            _make_mock_settings,
            write_sql_files,
        )
        from prefect_dbt.core._orchestrator import (
            ExecutionMode,
            PrefectDbtOrchestrator,
        )

        manifest_path = write_manifest(tmp_path, source_manifest_data)
        settings = _make_mock_settings(project_dir=tmp_path)
        executor = _make_mock_executor_per_node(success=True)

        # Write SQL files so cache policy can hash them
        write_sql_files(
            tmp_path,
            {
                "models/stg_src_customers.sql": "select * from {{ source('raw', 'customers') }}",
                "models/stg_src_orders.sql": "select * from {{ source('raw', 'orders') }}",
                "models/src_customer_summary.sql": "select * from {{ ref('stg_src_customers') }}",
            },
        )

        # Write sources.json
        target_dir = manifest_path.parent
        write_sources_json(
            target_dir,
            [
                {
                    "unique_id": "source.test.raw.customers",
                    "status": "pass",
                    "max_loaded_at_time_ago_in_s": 3600.0,  # 1 hour ago
                    "criteria": {
                        "warn_after": {"count": 6, "period": "hour"},
                    },
                },
                {
                    "unique_id": "source.test.raw.orders",
                    "status": "pass",
                    "max_loaded_at_time_ago_in_s": 1800.0,  # 30 min ago
                    "criteria": {
                        "warn_after": {"count": 12, "period": "hour"},
                    },
                },
            ],
        )

        from prefect.task_runners import ThreadPoolTaskRunner

        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=manifest_path,
            executor=executor,
            execution_mode=ExecutionMode.PER_NODE,
            enable_caching=True,
            use_source_freshness_expiration=True,
            task_runner_type=ThreadPoolTaskRunner,
            result_storage=tmp_path / "results",
            cache_key_storage=str(tmp_path / "keys"),
        )
        (tmp_path / "results").mkdir()
        (tmp_path / "keys").mkdir()

        from prefect import flow

        freshness_data = self._make_freshness_results(target_dir / "sources.json")

        with patch(
            "prefect_dbt.core._freshness.run_source_freshness",
            return_value=freshness_data,
        ):

            @flow
            def test_flow():
                return orch.run_build()

            results = test_flow()

        # All nodes should succeed
        for node_id, result in results.items():
            assert result["status"] == "success", f"{node_id}: {result.get('error')}"

    def test_validation_freshness_expiration_requires_caching(self):
        """use_source_freshness_expiration without caching raises ValueError."""
        from conftest import _make_mock_settings
        from prefect_dbt.core._orchestrator import PrefectDbtOrchestrator

        settings = _make_mock_settings()
        with pytest.raises(ValueError, match="use_source_freshness_expiration"):
            PrefectDbtOrchestrator(
                settings=settings,
                use_source_freshness_expiration=True,
                enable_caching=False,
            )
