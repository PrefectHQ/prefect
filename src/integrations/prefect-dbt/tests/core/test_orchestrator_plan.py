"""Tests for PrefectDbtOrchestrator.plan() dry-run method."""

from unittest.mock import patch

import pytest
from conftest import (
    _make_mock_executor,
    _make_mock_settings,
    write_manifest,
    write_sql_files,
)
from dbt.artifacts.resources.types import NodeType
from prefect_dbt.core._manifest import DbtNode, ExecutionWave
from prefect_dbt.core._orchestrator import (
    BuildPlan,
    CacheConfig,
    ExecutionMode,
    PrefectDbtOrchestrator,
    TestStrategy,
)

# =============================================================================
# TestPlanBasic
# =============================================================================


class TestPlanBasic:
    def test_empty_manifest(self, tmp_path):
        """Empty manifest produces an empty plan."""
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        plan = orch.plan()

        assert isinstance(plan, BuildPlan)
        assert plan.waves == ()
        assert plan.node_count == 0
        assert plan.estimated_parallelism == 0
        assert plan.skipped_nodes == {}
        assert plan.cache_predictions is None

    def test_single_node(self, tmp_path):
        """Single-node manifest produces one wave with one node."""
        manifest = write_manifest(
            tmp_path,
            {
                "nodes": {
                    "model.test.m1": {
                        "name": "m1",
                        "resource_type": "model",
                        "depends_on": {"nodes": []},
                        "config": {"materialized": "table"},
                    },
                },
                "sources": {},
            },
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        plan = orch.plan()

        assert plan.node_count == 1
        assert len(plan.waves) == 1
        assert plan.estimated_parallelism == 1
        assert plan.waves[0].wave_number == 0
        assert plan.waves[0].nodes[0].unique_id == "model.test.m1"

    def test_diamond_graph(self, tmp_path, diamond_manifest_data):
        """Diamond graph: root -> left/right -> leaf produces 3 waves."""
        manifest = write_manifest(tmp_path, diamond_manifest_data)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        plan = orch.plan()

        assert plan.node_count == 4
        assert len(plan.waves) == 3
        # Wave 0: root (1 node), Wave 1: left+right (2 nodes), Wave 2: leaf (1 node)
        assert plan.estimated_parallelism == 2
        wave_0_ids = {n.unique_id for n in plan.waves[0].nodes}
        wave_1_ids = {n.unique_id for n in plan.waves[1].nodes}
        wave_2_ids = {n.unique_id for n in plan.waves[2].nodes}
        assert wave_0_ids == {"model.test.root"}
        assert wave_1_ids == {"model.test.left", "model.test.right"}
        assert wave_2_ids == {"model.test.leaf"}

    def test_linear_chain(self, tmp_path, linear_manifest_data):
        """Linear chain a -> b -> c produces 3 waves, parallelism 1."""
        manifest = write_manifest(tmp_path, linear_manifest_data)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        plan = orch.plan()

        assert plan.node_count == 3
        assert len(plan.waves) == 3
        assert plan.estimated_parallelism == 1

    def test_plan_returns_frozen_dataclass(self, tmp_path):
        """BuildPlan is frozen (immutable)."""
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        plan = orch.plan()

        with pytest.raises(AttributeError):
            plan.node_count = 99  # type: ignore[misc]

    def test_no_cache_predictions_without_cache_config(self, tmp_path):
        """cache_predictions is None when no CacheConfig is set."""
        manifest = write_manifest(
            tmp_path,
            {
                "nodes": {
                    "model.test.m1": {
                        "name": "m1",
                        "resource_type": "model",
                        "depends_on": {"nodes": []},
                        "config": {"materialized": "table"},
                    },
                },
                "sources": {},
            },
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        plan = orch.plan()

        assert plan.cache_predictions is None


# =============================================================================
# TestPlanWithSelectors
# =============================================================================


class TestPlanWithSelectors:
    @patch("prefect_dbt.core._orchestrator.resolve_selection")
    def test_select_filters_nodes(self, mock_resolve, tmp_path, diamond_manifest_data):
        """plan() with select= filters to only selected nodes."""
        manifest = write_manifest(tmp_path, diamond_manifest_data)
        mock_resolve.return_value = {"model.test.root", "model.test.left"}

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        plan = orch.plan(select="tag:daily")

        assert plan.node_count == 2
        all_ids = {n.unique_id for w in plan.waves for n in w.nodes}
        assert all_ids == {"model.test.root", "model.test.left"}
        mock_resolve.assert_called_once()

    @patch("prefect_dbt.core._orchestrator.resolve_selection")
    def test_no_selectors_skips_resolve(self, mock_resolve, tmp_path):
        """plan() without select/exclude doesn't call resolve_selection."""
        manifest = write_manifest(
            tmp_path,
            {
                "nodes": {
                    "model.test.m1": {
                        "name": "m1",
                        "resource_type": "model",
                        "depends_on": {"nodes": []},
                        "config": {"materialized": "table"},
                    },
                },
                "sources": {},
            },
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        orch.plan()

        mock_resolve.assert_not_called()


# =============================================================================
# TestPlanTestStrategies
# =============================================================================


DIAMOND_WITH_TESTS = {
    "nodes": {
        "model.test.root": {
            "name": "root",
            "resource_type": "model",
            "depends_on": {"nodes": []},
            "config": {"materialized": "table"},
        },
        "model.test.leaf": {
            "name": "leaf",
            "resource_type": "model",
            "depends_on": {"nodes": ["model.test.root"]},
            "config": {"materialized": "table"},
        },
        "test.test.not_null_root_id": {
            "name": "not_null_root_id",
            "resource_type": "test",
            "depends_on": {"nodes": ["model.test.root"]},
            "config": {},
        },
    },
    "sources": {},
}


class TestPlanTestStrategies:
    def test_skip_excludes_tests(self, tmp_path):
        """SKIP strategy excludes test nodes from plan."""
        manifest = write_manifest(tmp_path, DIAMOND_WITH_TESTS)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
            test_strategy=TestStrategy.SKIP,
        )

        plan = orch.plan()

        all_ids = {n.unique_id for w in plan.waves for n in w.nodes}
        assert "test.test.not_null_root_id" not in all_ids
        assert plan.node_count == 2

    def test_immediate_includes_tests_interleaved(self, tmp_path):
        """IMMEDIATE strategy interleaves tests with models."""
        manifest = write_manifest(tmp_path, DIAMOND_WITH_TESTS)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
            test_strategy=TestStrategy.IMMEDIATE,
        )

        plan = orch.plan()

        all_ids = {n.unique_id for w in plan.waves for n in w.nodes}
        assert "test.test.not_null_root_id" in all_ids
        # Test should be in a wave after root but before or with leaf
        assert plan.node_count == 3

    def test_deferred_appends_tests_after_models(self, tmp_path):
        """DEFERRED strategy places tests after all model waves."""
        manifest = write_manifest(tmp_path, DIAMOND_WITH_TESTS)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
            test_strategy=TestStrategy.DEFERRED,
        )

        plan = orch.plan()

        all_ids = {n.unique_id for w in plan.waves for n in w.nodes}
        assert "test.test.not_null_root_id" in all_ids
        assert plan.node_count == 3

        # Last wave should contain the test
        last_wave_ids = {n.unique_id for n in plan.waves[-1].nodes}
        assert "test.test.not_null_root_id" in last_wave_ids


# =============================================================================
# TestPlanWithFreshness
# =============================================================================


class TestPlanWithFreshness:
    @patch("prefect_dbt.core._orchestrator.filter_stale_nodes")
    @patch("prefect_dbt.core._orchestrator.run_source_freshness")
    def test_only_fresh_sources_filters_stale(
        self, mock_freshness, mock_filter, tmp_path, source_manifest_data
    ):
        """only_fresh_sources=True filters stale nodes and populates skipped_nodes."""
        manifest = write_manifest(tmp_path, source_manifest_data)

        # Simulate freshness results
        mock_freshness.return_value = {"source.test.raw.customers": {"status": "error"}}

        # Build nodes that would remain after filtering
        from prefect_dbt.core._manifest import ManifestParser

        parser = ManifestParser(manifest)
        all_nodes = parser.filter_nodes()
        # Keep only stg_src_orders and src_customer_summary, skip stg_src_customers
        remaining = {
            k: v for k, v in all_nodes.items() if k != "model.test.stg_src_customers"
        }
        skipped = {
            "model.test.stg_src_customers": {
                "status": "skipped",
                "reason": "stale upstream source",
            }
        }
        mock_filter.return_value = (remaining, skipped)

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        plan = orch.plan(only_fresh_sources=True)

        assert "model.test.stg_src_customers" in plan.skipped_nodes
        mock_freshness.assert_called_once()
        mock_filter.assert_called_once()


# =============================================================================
# TestPlanCachePredictions
# =============================================================================


class TestPlanCachePredictions:
    def _make_cache_orch(self, tmp_path, manifest_data, cache_config=None):
        """Helper to create a PER_NODE orchestrator with cache."""
        manifest = write_manifest(tmp_path, manifest_data)
        settings = _make_mock_settings(project_dir=tmp_path)
        if cache_config is None:
            cache_config = CacheConfig(key_storage=tmp_path / "cache")
        return PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=manifest,
            executor=_make_mock_executor(),
            execution_mode=ExecutionMode.PER_NODE,
            cache=cache_config,
        )

    def test_cache_predictions_all_miss_on_fresh_build(self, tmp_path):
        """First build with no execution state → all misses."""
        manifest_data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                    "original_file_path": "models/m1.sql",
                },
            },
            "sources": {},
        }
        write_sql_files(tmp_path, {"models/m1.sql": "SELECT 1"})
        (tmp_path / "cache").mkdir(exist_ok=True)

        orch = self._make_cache_orch(tmp_path, manifest_data)
        plan = orch.plan()

        assert plan.cache_predictions is not None
        assert plan.cache_predictions["model.test.m1"] == "miss"

    def test_cache_predictions_excluded_by_resource_type(self, tmp_path):
        """Test nodes are excluded from cache predictions by default."""
        manifest_data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                    "original_file_path": "models/m1.sql",
                },
                "test.test.t1": {
                    "name": "t1",
                    "resource_type": "test",
                    "depends_on": {"nodes": ["model.test.m1"]},
                    "config": {},
                },
            },
            "sources": {},
        }
        write_sql_files(tmp_path, {"models/m1.sql": "SELECT 1"})
        (tmp_path / "cache").mkdir(exist_ok=True)

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(project_dir=tmp_path),
            manifest_path=write_manifest(tmp_path, manifest_data),
            executor=_make_mock_executor(),
            execution_mode=ExecutionMode.PER_NODE,
            cache=CacheConfig(key_storage=tmp_path / "cache"),
            test_strategy=TestStrategy.IMMEDIATE,
        )

        plan = orch.plan()

        assert plan.cache_predictions is not None
        assert plan.cache_predictions.get("test.test.t1") == "excluded"

    def test_cache_predictions_excluded_by_materialization(self, tmp_path):
        """Incremental models are excluded from cache by default."""
        manifest_data = {
            "nodes": {
                "model.test.inc": {
                    "name": "inc",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "incremental"},
                    "original_file_path": "models/inc.sql",
                },
            },
            "sources": {},
        }
        write_sql_files(tmp_path, {"models/inc.sql": "SELECT 1"})
        (tmp_path / "cache").mkdir(exist_ok=True)

        orch = self._make_cache_orch(tmp_path, manifest_data)
        plan = orch.plan()

        assert plan.cache_predictions is not None
        assert plan.cache_predictions["model.test.inc"] == "excluded"

    def test_cache_predictions_hit_when_state_matches(self, tmp_path):
        """Cache prediction is 'hit' when execution state matches precomputed key."""
        import json

        manifest_data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                    "original_file_path": "models/m1.sql",
                },
            },
            "sources": {},
        }
        write_sql_files(tmp_path, {"models/m1.sql": "SELECT 1"})
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir(exist_ok=True)

        orch = self._make_cache_orch(tmp_path, manifest_data)

        # First, compute the key that _precompute_all_cache_keys would produce
        from prefect_dbt.core._manifest import ManifestParser

        parser = ManifestParser(write_manifest(tmp_path, manifest_data))
        precomputed = orch._precompute_all_cache_keys(
            parser.get_executable_nodes(), False, parser.get_macro_paths()
        )

        # Write execution state that matches
        state_path = cache_dir / ".execution_state.json"
        state_path.write_text(json.dumps(precomputed))

        plan = orch.plan()

        assert plan.cache_predictions is not None
        assert plan.cache_predictions["model.test.m1"] == "hit"

    def test_cache_predictions_miss_when_full_refresh(self, tmp_path):
        """full_refresh=True forces all predictions to 'miss' even with matching state."""
        import json

        manifest_data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                    "original_file_path": "models/m1.sql",
                },
            },
            "sources": {},
        }
        write_sql_files(tmp_path, {"models/m1.sql": "SELECT 1"})
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir(exist_ok=True)

        orch = self._make_cache_orch(tmp_path, manifest_data)

        from prefect_dbt.core._manifest import ManifestParser

        parser = ManifestParser(write_manifest(tmp_path, manifest_data))
        precomputed = orch._precompute_all_cache_keys(
            parser.get_executable_nodes(), False, parser.get_macro_paths()
        )

        # Write execution state that matches — would be "hit" without full_refresh
        state_path = cache_dir / ".execution_state.json"
        state_path.write_text(json.dumps(precomputed))

        plan = orch.plan(full_refresh=True)

        assert plan.cache_predictions is not None
        assert plan.cache_predictions["model.test.m1"] == "miss"


# =============================================================================
# TestPlanExtraCliArgs
# =============================================================================


class TestPlanExtraCliArgs:
    def test_blocked_flag_raises(self, tmp_path):
        """Blocked CLI args raise ValueError in plan() too."""
        manifest = write_manifest(
            tmp_path,
            {
                "nodes": {
                    "model.test.m1": {
                        "name": "m1",
                        "resource_type": "model",
                        "depends_on": {"nodes": []},
                        "config": {"materialized": "table"},
                    },
                },
                "sources": {},
            },
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        with pytest.raises(ValueError, match="--select"):
            orch.plan(extra_cli_args=["--select", "tag:foo"])

    def test_safe_flags_accepted(self, tmp_path):
        """Safe extra CLI args don't raise in plan()."""
        manifest = write_manifest(
            tmp_path,
            {
                "nodes": {
                    "model.test.m1": {
                        "name": "m1",
                        "resource_type": "model",
                        "depends_on": {"nodes": []},
                        "config": {"materialized": "table"},
                    },
                },
                "sources": {},
            },
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        # Should not raise
        plan = orch.plan(extra_cli_args=["--store-failures"])
        assert plan.node_count == 1


# =============================================================================
# TestPlanDoesNotExecute
# =============================================================================


class TestPlanDoesNotExecute:
    def test_executor_not_called(self, tmp_path, diamond_manifest_data):
        """plan() must not call executor.execute_wave or execute_node."""
        manifest = write_manifest(tmp_path, diamond_manifest_data)
        executor = _make_mock_executor()

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
        )

        orch.plan()

        executor.execute_wave.assert_not_called()
        assert not hasattr(executor, "execute_node") or not executor.execute_node.called


# =============================================================================
# TestPreparedBuildSharedWithRunBuild
# =============================================================================


class TestPreparedBuildSharedWithRunBuild:
    def test_run_build_still_works_after_refactor(self, tmp_path):
        """run_build() continues to work with the _prepare_build refactor."""
        manifest = write_manifest(
            tmp_path,
            {
                "nodes": {
                    "model.test.m1": {
                        "name": "m1",
                        "resource_type": "model",
                        "depends_on": {"nodes": []},
                        "config": {"materialized": "table"},
                    },
                },
                "sources": {},
            },
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        results = orch.run_build()

        assert "model.test.m1" in results
        assert results["model.test.m1"]["status"] == "success"

    def test_plan_and_run_build_see_same_waves(self, tmp_path, diamond_manifest_data):
        """plan() and run_build() produce consistent wave structures."""
        manifest = write_manifest(tmp_path, diamond_manifest_data)

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )

        plan = orch.plan()
        results = orch.run_build()

        # All nodes from the plan should appear in run_build results
        plan_ids = {n.unique_id for w in plan.waves for n in w.nodes}
        assert plan_ids == set(results.keys())


# =============================================================================
# TestBuildPlanStr
# =============================================================================


def _node(
    uid: str, resource_type: NodeType = NodeType.Model, materialization: str = "table"
) -> DbtNode:
    return DbtNode(
        unique_id=uid,
        name=uid.split(".")[-1],
        resource_type=resource_type,
        materialization=materialization,
    )


class TestBuildPlanStr:
    def test_empty_plan(self):
        plan = BuildPlan(
            waves=(),
            node_count=0,
            cache_predictions=None,
            skipped_nodes={},
            estimated_parallelism=0,
        )
        text = str(plan)
        assert "0 node(s) in 0 wave(s)" in text
        assert "max parallelism = 0" in text
        # No cache or skipped sections
        assert "Cache:" not in text
        assert "Skipped" not in text

    def test_single_wave_no_cache(self):
        m1 = _node("model.test.m1")
        plan = BuildPlan(
            waves=(ExecutionWave(wave_number=0, nodes=[m1]),),
            node_count=1,
            cache_predictions=None,
            skipped_nodes={},
            estimated_parallelism=1,
        )
        text = str(plan)
        assert "1 node(s) in 1 wave(s)" in text
        assert "Wave 0 (1 node(s))" in text
        assert "model.test.m1" in text
        assert "[model, table]" in text
        assert "Cache:" not in text

    def test_multiple_waves(self):
        m1 = _node("model.test.m1")
        m2 = _node("model.test.m2", materialization="view")
        m3 = _node("model.test.m3")
        plan = BuildPlan(
            waves=(
                ExecutionWave(wave_number=0, nodes=[m1, m2]),
                ExecutionWave(wave_number=1, nodes=[m3]),
            ),
            node_count=3,
            cache_predictions=None,
            skipped_nodes={},
            estimated_parallelism=2,
        )
        text = str(plan)
        assert "3 node(s) in 2 wave(s)" in text
        assert "max parallelism = 2" in text
        assert "Wave 0 (2 node(s))" in text
        assert "Wave 1 (1 node(s))" in text
        assert "[model, view]" in text

    def test_cache_predictions_displayed(self):
        m1 = _node("model.test.m1")
        m2 = _node("model.test.m2")
        t1 = _node("test.test.t1", resource_type=NodeType.Test, materialization="test")
        plan = BuildPlan(
            waves=(ExecutionWave(wave_number=0, nodes=[m1, m2, t1]),),
            node_count=3,
            cache_predictions={
                "model.test.m1": "hit",
                "model.test.m2": "miss",
                "test.test.t1": "excluded",
            },
            skipped_nodes={},
            estimated_parallelism=3,
        )
        text = str(plan)
        assert "(cache: hit)" in text
        assert "(cache: miss)" in text
        assert "(cache: excluded)" in text
        assert "1 hit(s), 1 miss(es), 1 excluded" in text

    def test_skipped_nodes_displayed(self):
        m1 = _node("model.test.m1")
        plan = BuildPlan(
            waves=(ExecutionWave(wave_number=0, nodes=[m1]),),
            node_count=1,
            cache_predictions=None,
            skipped_nodes={
                "model.test.stale": {"status": "skipped", "reason": "stale source"},
            },
            estimated_parallelism=1,
        )
        text = str(plan)
        assert "Skipped (1)" in text
        assert "model.test.stale: stale source" in text

    def test_str_matches_print_output(self, tmp_path):
        """str() on a plan from the orchestrator works end-to-end."""
        manifest = write_manifest(
            tmp_path,
            {
                "nodes": {
                    "model.test.m1": {
                        "name": "m1",
                        "resource_type": "model",
                        "depends_on": {"nodes": []},
                        "config": {"materialized": "table"},
                    },
                },
                "sources": {},
            },
        )
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )
        plan = orch.plan()
        text = str(plan)
        assert "1 node(s) in 1 wave(s)" in text
        assert "model.test.m1" in text
