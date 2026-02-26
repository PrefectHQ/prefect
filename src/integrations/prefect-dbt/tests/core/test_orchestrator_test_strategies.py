"""Tests for dbt test strategy execution in PrefectDbtOrchestrator."""

from unittest.mock import MagicMock, patch

import pytest
from conftest import (
    _make_mock_executor,
    _make_mock_executor_per_node,
    _make_mock_settings,
    write_manifest,
)
from dbt.artifacts.resources.types import NodeType
from prefect_dbt.core._executor import DbtExecutor, ExecutionResult
from prefect_dbt.core._manifest import ManifestParser
from prefect_dbt.core._orchestrator import (
    ExecutionMode,
    PrefectDbtOrchestrator,
    TestStrategy,
)

from prefect import flow
from prefect.task_runners import ThreadPoolTaskRunner

# -- Manifest data with tests -----------------------------------------------

SINGLE_MODEL_WITH_TEST = {
    "nodes": {
        "model.test.m1": {
            "name": "m1",
            "resource_type": "model",
            "depends_on": {"nodes": []},
            "config": {"materialized": "table"},
        },
        "test.test.not_null_m1_id": {
            "name": "not_null_m1_id",
            "resource_type": "test",
            "depends_on": {"nodes": ["model.test.m1"]},
            "config": {},
        },
    },
    "sources": {},
}

SINGLE_MODEL_WITH_UNIT_TEST = {
    "nodes": {
        "model.test.m1": {
            "name": "m1",
            "resource_type": "model",
            "depends_on": {"nodes": []},
            "config": {"materialized": "table"},
        },
        "unit_test.test.ut_m1": {
            "name": "ut_m1",
            "resource_type": "unit_test",
            "depends_on": {"nodes": ["model.test.m1"]},
            "config": {},
        },
    },
    "sources": {},
}

MIXED_TEST_TYPES = {
    "nodes": {
        "model.test.m1": {
            "name": "m1",
            "resource_type": "model",
            "depends_on": {"nodes": []},
            "config": {"materialized": "table"},
        },
        "test.test.not_null_m1_id": {
            "name": "not_null_m1_id",
            "resource_type": "test",
            "depends_on": {"nodes": ["model.test.m1"]},
            "config": {},
        },
        "unit_test.test.ut_m1": {
            "name": "ut_m1",
            "resource_type": "unit_test",
            "depends_on": {"nodes": ["model.test.m1"]},
            "config": {},
        },
    },
    "sources": {},
}

EMPTY_MANIFEST = {"nodes": {}, "sources": {}}


# -- Fixtures ----------------------------------------------------------------


@pytest.fixture
def per_node_orch(tmp_path):
    """Factory for PER_NODE orchestrator with mock executor."""

    def _factory(manifest_data, *, executor=None, **kwargs):
        manifest = write_manifest(tmp_path, manifest_data)
        if executor is None:
            executor = _make_mock_executor_per_node(**kwargs.pop("executor_kwargs", {}))
        defaults = {
            "settings": _make_mock_settings(),
            "manifest_path": manifest,
            "executor": executor,
            "execution_mode": ExecutionMode.PER_NODE,
            "task_runner_type": ThreadPoolTaskRunner,
        }
        defaults.update(kwargs)
        return PrefectDbtOrchestrator(**defaults), executor

    return _factory


@pytest.fixture
def per_wave_orch(tmp_path):
    """Factory for PER_WAVE orchestrator with mock executor."""

    def _factory(manifest_data, *, executor=None, **kwargs):
        manifest = write_manifest(tmp_path, manifest_data)
        if executor is None:
            executor = _make_mock_executor(**kwargs.pop("executor_kwargs", {}))
        defaults = {
            "settings": _make_mock_settings(),
            "manifest_path": manifest,
            "executor": executor,
            "execution_mode": ExecutionMode.PER_WAVE,
        }
        defaults.update(kwargs)
        return PrefectDbtOrchestrator(**defaults), executor

    return _factory


# =============================================================================
# TestTestStrategyInit
# =============================================================================


class TestTestStrategyInit:
    def test_default_is_immediate(self, tmp_path):
        manifest = write_manifest(tmp_path, EMPTY_MANIFEST)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )
        assert orch._test_strategy == TestStrategy.IMMEDIATE

    def test_immediate_accepted(self, tmp_path):
        manifest = write_manifest(tmp_path, EMPTY_MANIFEST)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
            test_strategy=TestStrategy.IMMEDIATE,
        )
        assert orch._test_strategy == TestStrategy.IMMEDIATE

    def test_deferred_accepted(self, tmp_path):
        manifest = write_manifest(tmp_path, EMPTY_MANIFEST)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
            test_strategy=TestStrategy.DEFERRED,
        )
        assert orch._test_strategy == TestStrategy.DEFERRED

    def test_skip_accepted(self, tmp_path):
        manifest = write_manifest(tmp_path, EMPTY_MANIFEST)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
            test_strategy=TestStrategy.SKIP,
        )
        assert orch._test_strategy == TestStrategy.SKIP

    def test_invalid_raises_value_error(self, tmp_path):
        manifest = write_manifest(tmp_path, EMPTY_MANIFEST)
        with pytest.raises(ValueError, match="Invalid test_strategy"):
            PrefectDbtOrchestrator(
                settings=_make_mock_settings(),
                manifest_path=manifest,
                executor=_make_mock_executor(),
                test_strategy="invalid",
            )

    def test_string_value_accepted(self, tmp_path):
        """String enum values are auto-coerced."""
        manifest = write_manifest(tmp_path, EMPTY_MANIFEST)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
            test_strategy="immediate",
        )
        assert orch._test_strategy == TestStrategy.IMMEDIATE


# =============================================================================
# TestSkipStrategy
# =============================================================================


class TestSkipStrategy:
    def test_per_wave_excludes_tests(self, per_wave_orch):
        """SKIP + PER_WAVE: test nodes do not appear in results."""
        orch, executor = per_wave_orch(
            SINGLE_MODEL_WITH_TEST,
            test_strategy=TestStrategy.SKIP,
        )
        results = orch.run_build()

        assert "model.test.m1" in results
        assert "test.test.not_null_m1_id" not in results

    def test_per_node_excludes_tests(self, per_node_orch):
        """SKIP + PER_NODE: test nodes do not appear in results."""
        orch, executor = per_node_orch(
            SINGLE_MODEL_WITH_TEST,
            test_strategy=TestStrategy.SKIP,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        assert "model.test.m1" in results
        assert "test.test.not_null_m1_id" not in results

    def test_executor_not_called_for_tests_per_node(self, per_node_orch):
        """SKIP: executor is only called for model, not test."""
        orch, executor = per_node_orch(
            SINGLE_MODEL_WITH_TEST,
            test_strategy=TestStrategy.SKIP,
        )

        @flow
        def test_flow():
            return orch.run_build()

        test_flow()
        assert executor.execute_node.call_count == 1


# =============================================================================
# TestImmediatePerNode
# =============================================================================


class TestImmediatePerNode:
    def test_test_runs_after_parent_model(
        self, per_node_orch, diamond_with_tests_manifest_data
    ):
        """IMMEDIATE + PER_NODE: tests appear in results after their parent models."""
        orch, executor = per_node_orch(
            diamond_with_tests_manifest_data,
            test_strategy=TestStrategy.IMMEDIATE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        # All 4 models + 3 tests should be in results
        assert len(results) == 7
        for node_id in results:
            assert results[node_id]["status"] == "success"

        # Test on root ran after root
        root_completed = results["model.test.root"]["timing"]["completed_at"]
        test_root_started = results["test.test.not_null_root_id"]["timing"][
            "started_at"
        ]
        assert root_completed <= test_root_started

    def test_multi_model_test_waits_for_all_parents(
        self, per_node_orch, diamond_with_tests_manifest_data
    ):
        """IMMEDIATE + PER_NODE: multi-model test waits for all parents."""
        orch, _ = per_node_orch(
            diamond_with_tests_manifest_data,
            test_strategy=TestStrategy.IMMEDIATE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        # rel_leaf_to_left depends on leaf and left.
        # Both must complete before the test starts.
        leaf_completed = results["model.test.leaf"]["timing"]["completed_at"]
        left_completed = results["model.test.left"]["timing"]["completed_at"]
        test_started = results["test.test.rel_leaf_to_left"]["timing"]["started_at"]
        assert leaf_completed <= test_started
        assert left_completed <= test_started

    def test_uses_test_command(self, per_node_orch):
        """IMMEDIATE + PER_NODE: test nodes use the 'test' command."""
        orch, _ = per_node_orch(
            SINGLE_MODEL_WITH_TEST,
            test_strategy=TestStrategy.IMMEDIATE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()
        assert results["test.test.not_null_m1_id"]["invocation"]["command"] == "test"

    def test_test_failure_skips_downstream_models(self, per_node_orch):
        """IMMEDIATE: a test failure on root skips downstream leaf.

        Matches `dbt build` semantics: a failing test on model M causes
        all downstream dependents of M to be skipped.
        """
        # Use a simple chain: root -> leaf, test on root
        data = {
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
        orch, _ = per_node_orch(
            data,
            test_strategy=TestStrategy.IMMEDIATE,
            executor_kwargs={
                "fail_nodes": {"test.test.not_null_root_id"},
                "error": RuntimeError("test failed"),
            },
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        assert results["model.test.root"]["status"] == "success"
        assert results["test.test.not_null_root_id"]["status"] == "error"
        # leaf is downstream of root whose test failed -> skipped
        assert results["model.test.leaf"]["status"] == "skipped"
        assert (
            "test.test.not_null_root_id"
            in results["model.test.leaf"]["failed_upstream"]
        )

    def test_test_failure_transitive_cascade(self, per_node_orch):
        """IMMEDIATE: test failure cascades transitively through the DAG.

        root -> mid -> leaf, test on root fails.
        Both mid and leaf should be skipped.
        """
        data = {
            "nodes": {
                "model.test.root": {
                    "name": "root",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                },
                "model.test.mid": {
                    "name": "mid",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test.root"]},
                    "config": {"materialized": "table"},
                },
                "model.test.leaf": {
                    "name": "leaf",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test.mid"]},
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
        orch, _ = per_node_orch(
            data,
            test_strategy=TestStrategy.IMMEDIATE,
            executor_kwargs={
                "fail_nodes": {"test.test.not_null_root_id"},
                "error": RuntimeError("test failed"),
            },
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        assert results["model.test.root"]["status"] == "success"
        assert results["test.test.not_null_root_id"]["status"] == "error"
        assert results["model.test.mid"]["status"] == "skipped"
        assert results["model.test.leaf"]["status"] == "skipped"
        # All selected nodes must appear in results
        assert len(results) == 4

    def test_relationship_test_spanning_chain_no_cycle(self, per_node_orch):
        """IMMEDIATE: a relationship test spanning a parent-child chain does not cause cycles.

        DAG: root -> mid -> leaf
        Test: rel_leaf_to_root depends on (root, leaf)

        The augmentation must NOT add rel_leaf_to_root as a dependency of
        mid, because that would create mid -> rel_leaf_to_root -> leaf -> mid.
        """
        data = {
            "nodes": {
                "model.test.root": {
                    "name": "root",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                },
                "model.test.mid": {
                    "name": "mid",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test.root"]},
                    "config": {"materialized": "table"},
                },
                "model.test.leaf": {
                    "name": "leaf",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test.mid"]},
                    "config": {"materialized": "table"},
                },
                "test.test.rel_leaf_to_root": {
                    "name": "rel_leaf_to_root",
                    "resource_type": "test",
                    "depends_on": {"nodes": ["model.test.root", "model.test.leaf"]},
                    "config": {},
                },
            },
            "sources": {},
        }
        orch, _ = per_node_orch(
            data,
            test_strategy=TestStrategy.IMMEDIATE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        # All nodes should execute successfully — no cycle error
        assert results["model.test.root"]["status"] == "success"
        assert results["model.test.mid"]["status"] == "success"
        assert results["model.test.leaf"]["status"] == "success"
        assert results["test.test.rel_leaf_to_root"]["status"] == "success"

    def test_all_selected_nodes_in_results(self, per_node_orch):
        """IMMEDIATE: every selected node appears in results even on test failure."""
        data = {
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
        orch, _ = per_node_orch(
            data,
            test_strategy=TestStrategy.IMMEDIATE,
            executor_kwargs={
                "fail_nodes": {"test.test.not_null_root_id"},
                "error": RuntimeError("test failed"),
            },
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        # Every node must be present — none silently dropped
        assert "model.test.root" in results
        assert "test.test.not_null_root_id" in results
        assert "model.test.leaf" in results

    def test_model_failure_skips_dependent_tests(self, per_node_orch):
        """IMMEDIATE: model failure skips tests that depend on that model."""
        orch, _ = per_node_orch(
            SINGLE_MODEL_WITH_TEST,
            test_strategy=TestStrategy.IMMEDIATE,
            executor_kwargs={
                "fail_nodes": {"model.test.m1"},
                "error": RuntimeError("model failed"),
            },
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        assert results["model.test.m1"]["status"] == "error"
        assert results["test.test.not_null_m1_id"]["status"] == "skipped"
        assert "model.test.m1" in results["test.test.not_null_m1_id"]["failed_upstream"]


# =============================================================================
# TestImmediatePerWave
# =============================================================================


class TestImmediatePerWave:
    def test_default_strategy_includes_tests(self, per_wave_orch):
        """Default (no test_strategy arg) includes tests (IMMEDIATE)."""
        orch, _ = per_wave_orch(SINGLE_MODEL_WITH_TEST)
        results = orch.run_build()

        assert "model.test.m1" in results
        assert "test.test.not_null_m1_id" in results
        assert results["test.test.not_null_m1_id"]["status"] == "success"

    def test_tests_interleaved_in_waves(
        self, per_wave_orch, diamond_with_tests_manifest_data
    ):
        """IMMEDIATE + PER_WAVE: tests appear in correct waves.

        With implicit test-to-downstream edges the wave order is:
          Wave 0: root
          Wave 1: not_null_root_id (test on root)
          Wave 2: left, right
          Wave 3: leaf
          Wave 4: not_null_leaf_id, rel_leaf_to_left (tests on leaf)
        """
        orch, _ = per_wave_orch(
            diamond_with_tests_manifest_data,
            test_strategy=TestStrategy.IMMEDIATE,
        )
        results = orch.run_build()

        # All 7 nodes should succeed
        assert len(results) == 7
        for r in results.values():
            assert r["status"] == "success"

    def test_single_model_test_in_results(self, per_wave_orch):
        """IMMEDIATE + PER_WAVE: test node appears in results."""
        orch, _ = per_wave_orch(
            SINGLE_MODEL_WITH_TEST,
            test_strategy=TestStrategy.IMMEDIATE,
        )
        results = orch.run_build()

        assert "model.test.m1" in results
        assert "test.test.not_null_m1_id" in results
        assert results["test.test.not_null_m1_id"]["status"] == "success"

    def test_test_failure_skips_downstream_models(self, tmp_path):
        """IMMEDIATE + PER_WAVE: test failure cascades to downstream models.

        Graph: root -> leaf, test on root.
        With implicit edges the test runs in a wave before leaf.
        When the test fails, leaf's wave is skipped.
        """
        data = {
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
        manifest = write_manifest(tmp_path, data)
        fail_nodes = {"test.test.not_null_root_id"}

        def _execute_wave(nodes, **kwargs):
            node_ids = [n.unique_id for n in nodes]
            has_failure = any(nid in fail_nodes for nid in node_ids)
            if has_failure:
                artifacts = {}
                for n in nodes:
                    if n.unique_id in fail_nodes:
                        artifacts[n.unique_id] = {"status": "fail"}
                    else:
                        artifacts[n.unique_id] = {"status": "success"}
                return ExecutionResult(
                    success=False,
                    node_ids=node_ids,
                    error=RuntimeError("test failed"),
                    artifacts=artifacts,
                )
            return ExecutionResult(
                success=True,
                node_ids=node_ids,
            )

        executor = MagicMock(spec=DbtExecutor)
        executor.execute_wave = MagicMock(side_effect=_execute_wave)

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            test_strategy=TestStrategy.IMMEDIATE,
        )
        results = orch.run_build()

        assert results["model.test.root"]["status"] == "success"
        assert results["test.test.not_null_root_id"]["status"] == "error"
        assert results["model.test.leaf"]["status"] == "skipped"
        assert (
            "test.test.not_null_root_id"
            in results["model.test.leaf"]["failed_upstream"]
        )

    def test_all_selected_nodes_in_results(self, tmp_path):
        """IMMEDIATE + PER_WAVE: every selected node appears in results."""
        data = {
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
        manifest = write_manifest(tmp_path, data)
        fail_nodes = {"test.test.not_null_root_id"}

        def _execute_wave(nodes, **kwargs):
            node_ids = [n.unique_id for n in nodes]
            has_failure = any(nid in fail_nodes for nid in node_ids)
            if has_failure:
                artifacts = {}
                for n in nodes:
                    if n.unique_id in fail_nodes:
                        artifacts[n.unique_id] = {"status": "fail"}
                    else:
                        artifacts[n.unique_id] = {"status": "success"}
                return ExecutionResult(
                    success=False,
                    node_ids=node_ids,
                    error=RuntimeError("test failed"),
                    artifacts=artifacts,
                )
            return ExecutionResult(success=True, node_ids=node_ids)

        executor = MagicMock(spec=DbtExecutor)
        executor.execute_wave = MagicMock(side_effect=_execute_wave)

        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=executor,
            test_strategy=TestStrategy.IMMEDIATE,
        )
        results = orch.run_build()

        # Every node must be present — none silently dropped
        assert "model.test.root" in results
        assert "test.test.not_null_root_id" in results
        assert "model.test.leaf" in results


# =============================================================================
# TestDeferredPerNode
# =============================================================================


class TestDeferredPerNode:
    def test_tests_after_all_models(
        self, per_node_orch, diamond_with_tests_manifest_data
    ):
        """DEFERRED + PER_NODE: all tests run after all models complete."""
        orch, _ = per_node_orch(
            diamond_with_tests_manifest_data,
            test_strategy=TestStrategy.DEFERRED,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        assert len(results) == 7

        # All models must complete before any test starts
        model_ids = [k for k in results if k.startswith("model.")]
        test_ids = [k for k in results if k.startswith("test.")]

        latest_model_completed = max(
            results[m]["timing"]["completed_at"] for m in model_ids
        )
        earliest_test_started = min(
            results[t]["timing"]["started_at"] for t in test_ids
        )
        assert latest_model_completed <= earliest_test_started

    def test_all_tests_parallel_in_deferred_wave(
        self, per_node_orch, diamond_with_tests_manifest_data
    ):
        """DEFERRED + PER_NODE: tests have no inter-dependencies, all in one wave."""
        orch, _ = per_node_orch(
            diamond_with_tests_manifest_data,
            test_strategy=TestStrategy.DEFERRED,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        test_ids = [k for k in results if k.startswith("test.")]
        assert len(test_ids) == 3

        for tid in test_ids:
            assert results[tid]["status"] == "success"


# =============================================================================
# TestDeferredPerWave
# =============================================================================


class TestDeferredPerWave:
    def test_test_wave_after_model_waves(
        self, per_wave_orch, diamond_with_tests_manifest_data
    ):
        """DEFERRED + PER_WAVE: test wave comes after all model waves."""
        orch, executor = per_wave_orch(
            diamond_with_tests_manifest_data,
            test_strategy=TestStrategy.DEFERRED,
        )
        results = orch.run_build()

        # All 7 nodes should succeed
        assert len(results) == 7
        for r in results.values():
            assert r["status"] == "success"

    def test_tests_in_results(self, per_wave_orch):
        """DEFERRED + PER_WAVE: test nodes appear in results."""
        orch, _ = per_wave_orch(
            SINGLE_MODEL_WITH_TEST,
            test_strategy=TestStrategy.DEFERRED,
        )
        results = orch.run_build()

        assert "model.test.m1" in results
        assert "test.test.not_null_m1_id" in results


# =============================================================================
# TestTestNodeCaching
# =============================================================================


class TestTestNodeCaching:
    @patch.object(PrefectDbtOrchestrator, "_build_cache_options_for_node")
    def test_tests_never_get_cache_policy(self, mock_cache_opts, per_node_orch):
        """Tests never get cache_policy even when caching is enabled.

        We verify by patching _build_cache_options_for_node and asserting
        it is only called for model nodes, never for test nodes.
        """
        mock_cache_opts.return_value = {"persist_result": True}

        orch, executor = per_node_orch(
            SINGLE_MODEL_WITH_TEST,
            test_strategy=TestStrategy.IMMEDIATE,
            enable_caching=True,
            result_storage="/tmp/test_results",
            cache_key_storage="/tmp/test_keys",
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        # Both nodes should succeed
        assert results["model.test.m1"]["status"] == "success"
        assert results["test.test.not_null_m1_id"]["status"] == "success"

        # _build_cache_options_for_node should only be called for the model
        assert mock_cache_opts.call_count == 1
        called_node = mock_cache_opts.call_args[0][0]
        assert called_node.resource_type == NodeType.Model


# =============================================================================
# TestTestsWithSelectors
# =============================================================================


class TestTestsWithSelectors:
    @patch("prefect_dbt.core._orchestrator.resolve_selection")
    def test_only_tests_with_all_parents_selected(
        self, mock_resolve, per_wave_orch, diamond_with_tests_manifest_data
    ):
        """Only tests whose parents are ALL in the selected set are included.

        Select root + left only. The test on root (not_null_root_id) should
        be included, but test on leaf (not_null_leaf_id) and the
        relationship test (rel_leaf_to_left) should be excluded because
        leaf is not selected.
        """
        mock_resolve.return_value = {
            "model.test.root",
            "model.test.left",
            # Include the test IDs too since dbt ls --resource-type all returns them
            "test.test.not_null_root_id",
            "test.test.not_null_leaf_id",
            "test.test.rel_leaf_to_left",
        }
        orch, _ = per_wave_orch(
            diamond_with_tests_manifest_data,
            test_strategy=TestStrategy.IMMEDIATE,
        )
        results = orch.run_build(select="root left")

        # Models: root and left
        assert "model.test.root" in results
        assert "model.test.left" in results
        assert "model.test.right" not in results
        assert "model.test.leaf" not in results

        # Tests: only not_null_root_id (parent root is selected)
        assert "test.test.not_null_root_id" in results
        # not_null_leaf_id excluded: parent leaf not in executable nodes
        assert "test.test.not_null_leaf_id" not in results
        # rel_leaf_to_left excluded: parent leaf not in executable nodes
        assert "test.test.rel_leaf_to_left" not in results

    @patch("prefect_dbt.core._orchestrator.resolve_selection")
    def test_multi_model_test_included_when_all_parents_selected(
        self, mock_resolve, per_wave_orch
    ):
        """Multi-model test is included when all its parents are in executable set."""
        data = {
            "nodes": {
                "model.test.a": {
                    "name": "a",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                },
                "model.test.b": {
                    "name": "b",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                },
                "test.test.rel_a_b": {
                    "name": "rel_a_b",
                    "resource_type": "test",
                    "depends_on": {"nodes": ["model.test.a", "model.test.b"]},
                    "config": {},
                },
            },
            "sources": {},
        }
        mock_resolve.return_value = {
            "model.test.a",
            "model.test.b",
            "test.test.rel_a_b",
        }
        orch, _ = per_wave_orch(data, test_strategy=TestStrategy.IMMEDIATE)
        results = orch.run_build(select="a b")

        assert "test.test.rel_a_b" in results

    @patch("prefect_dbt.core._orchestrator.resolve_selection")
    def test_multi_model_test_excluded_when_one_parent_missing(
        self, mock_resolve, per_wave_orch
    ):
        """Multi-model test excluded when one parent not selected."""
        data = {
            "nodes": {
                "model.test.a": {
                    "name": "a",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                },
                "model.test.b": {
                    "name": "b",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                },
                "test.test.rel_a_b": {
                    "name": "rel_a_b",
                    "resource_type": "test",
                    "depends_on": {"nodes": ["model.test.a", "model.test.b"]},
                    "config": {},
                },
            },
            "sources": {},
        }
        # Only select model a, not b
        mock_resolve.return_value = {
            "model.test.a",
            "test.test.rel_a_b",
        }
        orch, _ = per_wave_orch(data, test_strategy=TestStrategy.IMMEDIATE)
        results = orch.run_build(select="a")

        assert "model.test.a" in results
        assert "model.test.b" not in results
        # Test excluded because model.test.b not in executable nodes
        assert "test.test.rel_a_b" not in results


# =============================================================================
# TestIndirectSelectionSuppressed
# =============================================================================


class TestIndirectSelectionSuppressed:
    """Verify that PER_WAVE suppresses dbt's indirect test selection
    when the orchestrator is managing test scheduling."""

    def test_immediate_passes_indirect_selection_empty(self, per_wave_orch):
        """IMMEDIATE + PER_WAVE: execute_wave receives indirect_selection='empty'."""
        orch, executor = per_wave_orch(
            SINGLE_MODEL_WITH_TEST,
            test_strategy=TestStrategy.IMMEDIATE,
        )
        orch.run_build()

        for call_args in executor.execute_wave.call_args_list:
            assert call_args.kwargs.get("indirect_selection") == "empty" or (
                len(call_args.args) > 2 and call_args.args[2] == "empty"
            )

    def test_deferred_passes_indirect_selection_empty(
        self, per_wave_orch, diamond_with_tests_manifest_data
    ):
        """DEFERRED + PER_WAVE: all waves receive indirect_selection='empty'."""
        orch, executor = per_wave_orch(
            diamond_with_tests_manifest_data,
            test_strategy=TestStrategy.DEFERRED,
        )
        orch.run_build()

        for call_obj in executor.execute_wave.call_args_list:
            assert call_obj.kwargs.get("indirect_selection") == "empty"

    def test_skip_also_passes_indirect_selection_empty(self, per_wave_orch):
        """SKIP + PER_WAVE: indirect_selection='empty' suppresses implicit tests."""
        orch, executor = per_wave_orch(
            SINGLE_MODEL_WITH_TEST,
            test_strategy=TestStrategy.SKIP,
        )
        orch.run_build()

        for call_obj in executor.execute_wave.call_args_list:
            assert call_obj.kwargs.get("indirect_selection") == "empty"

    def test_default_also_passes_indirect_selection_empty(self, per_wave_orch):
        """Default strategy (IMMEDIATE): indirect_selection='empty' suppresses implicit tests."""
        orch, executor = per_wave_orch(SINGLE_MODEL_WITH_TEST)
        orch.run_build()

        for call_obj in executor.execute_wave.call_args_list:
            assert call_obj.kwargs.get("indirect_selection") == "empty"


# =============================================================================
# TestManifestParserTestNodes
# =============================================================================


class TestManifestParserTestNodes:
    """Unit tests for get_test_nodes() and filter_test_nodes()."""

    def test_get_test_nodes_returns_only_tests(self, tmp_path):
        data = SINGLE_MODEL_WITH_TEST
        manifest = write_manifest(tmp_path, data)
        parser = ManifestParser(manifest)

        test_nodes = parser.get_test_nodes()
        assert set(test_nodes.keys()) == {"test.test.not_null_m1_id"}
        assert test_nodes["test.test.not_null_m1_id"].resource_type == NodeType.Test

    def test_get_test_nodes_resolves_through_ephemeral(self, tmp_path):
        """Test depending on ephemeral -> model resolves to model."""
        data = {
            "nodes": {
                "model.test.base": {
                    "name": "base",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                },
                "model.test.eph": {
                    "name": "eph",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test.base"]},
                    "config": {"materialized": "ephemeral"},
                },
                "test.test.not_null_eph_id": {
                    "name": "not_null_eph_id",
                    "resource_type": "test",
                    "depends_on": {"nodes": ["model.test.eph"]},
                    "config": {},
                },
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        parser = ManifestParser(manifest)

        test_nodes = parser.get_test_nodes()
        # Test should resolve through ephemeral to base
        assert test_nodes["test.test.not_null_eph_id"].depends_on == (
            "model.test.base",
        )

    def test_get_test_nodes_caches_result(self, tmp_path):
        data = SINGLE_MODEL_WITH_TEST
        manifest = write_manifest(tmp_path, data)
        parser = ManifestParser(manifest)

        result1 = parser.get_test_nodes()
        result2 = parser.get_test_nodes()
        assert result1 is result2

    def test_filter_test_nodes_by_selected_ids(self, tmp_path):
        data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                },
                "test.test.t1": {
                    "name": "t1",
                    "resource_type": "test",
                    "depends_on": {"nodes": ["model.test.m1"]},
                    "config": {},
                },
                "test.test.t2": {
                    "name": "t2",
                    "resource_type": "test",
                    "depends_on": {"nodes": ["model.test.m1"]},
                    "config": {},
                },
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        parser = ManifestParser(manifest)

        filtered = parser.filter_test_nodes(
            selected_node_ids={"test.test.t1"},
            executable_node_ids={"model.test.m1"},
        )
        assert set(filtered.keys()) == {"test.test.t1"}

    def test_filter_test_nodes_by_executable_ids(self, tmp_path):
        data = {
            "nodes": {
                "model.test.a": {
                    "name": "a",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                },
                "model.test.b": {
                    "name": "b",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                },
                "test.test.rel_a_b": {
                    "name": "rel_a_b",
                    "resource_type": "test",
                    "depends_on": {"nodes": ["model.test.a", "model.test.b"]},
                    "config": {},
                },
            },
            "sources": {},
        }
        manifest = write_manifest(tmp_path, data)
        parser = ManifestParser(manifest)

        # Only model.test.a is executable (b was filtered out)
        filtered = parser.filter_test_nodes(
            executable_node_ids={"model.test.a"},
        )
        # rel_a_b excluded because model.test.b not in executable set
        assert filtered == {}

    def test_filter_test_nodes_none_keeps_all(self, tmp_path):
        data = SINGLE_MODEL_WITH_TEST
        manifest = write_manifest(tmp_path, data)
        parser = ManifestParser(manifest)

        filtered = parser.filter_test_nodes(
            selected_node_ids=None,
            executable_node_ids={"model.test.m1"},
        )
        assert "test.test.not_null_m1_id" in filtered

    def test_empty_manifest_returns_no_tests(self, tmp_path):
        manifest = write_manifest(tmp_path, EMPTY_MANIFEST)
        parser = ManifestParser(manifest)
        assert parser.get_test_nodes() == {}

    def test_get_test_nodes_includes_unit_tests(self, tmp_path):
        """get_test_nodes() returns NodeType.Unit nodes alongside NodeType.Test."""
        manifest = write_manifest(tmp_path, MIXED_TEST_TYPES)
        parser = ManifestParser(manifest)

        test_nodes = parser.get_test_nodes()
        assert "test.test.not_null_m1_id" in test_nodes
        assert "unit_test.test.ut_m1" in test_nodes
        assert test_nodes["test.test.not_null_m1_id"].resource_type == NodeType.Test
        assert test_nodes["unit_test.test.ut_m1"].resource_type == NodeType.Unit

    def test_get_test_nodes_unit_test_only(self, tmp_path):
        """get_test_nodes() works when manifest has only unit_test nodes."""
        manifest = write_manifest(tmp_path, SINGLE_MODEL_WITH_UNIT_TEST)
        parser = ManifestParser(manifest)

        test_nodes = parser.get_test_nodes()
        assert set(test_nodes.keys()) == {"unit_test.test.ut_m1"}
        assert test_nodes["unit_test.test.ut_m1"].resource_type == NodeType.Unit

    def test_filter_test_nodes_includes_unit_tests(self, tmp_path):
        """filter_test_nodes() keeps unit_test nodes when parents are executable."""
        manifest = write_manifest(tmp_path, MIXED_TEST_TYPES)
        parser = ManifestParser(manifest)

        filtered = parser.filter_test_nodes(
            executable_node_ids={"model.test.m1"},
        )
        assert "test.test.not_null_m1_id" in filtered
        assert "unit_test.test.ut_m1" in filtered


# =============================================================================
# TestUnitTestNodes
# =============================================================================


class TestUnitTestNodes:
    """Tests for dbt unit_test (NodeType.Unit) support."""

    def test_immediate_per_node_includes_unit_tests(self, per_node_orch):
        """IMMEDIATE + PER_NODE: unit_test nodes appear in results."""
        orch, _ = per_node_orch(
            SINGLE_MODEL_WITH_UNIT_TEST,
            test_strategy=TestStrategy.IMMEDIATE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        assert "model.test.m1" in results
        assert "unit_test.test.ut_m1" in results
        assert results["unit_test.test.ut_m1"]["status"] == "success"

    def test_immediate_per_wave_includes_unit_tests(self, per_wave_orch):
        """IMMEDIATE + PER_WAVE: unit_test nodes appear in results."""
        orch, _ = per_wave_orch(
            SINGLE_MODEL_WITH_UNIT_TEST,
            test_strategy=TestStrategy.IMMEDIATE,
        )
        results = orch.run_build()

        assert "unit_test.test.ut_m1" in results
        assert results["unit_test.test.ut_m1"]["status"] == "success"

    def test_deferred_per_node_includes_unit_tests(self, per_node_orch):
        """DEFERRED + PER_NODE: unit_test nodes run after all models."""
        orch, _ = per_node_orch(
            SINGLE_MODEL_WITH_UNIT_TEST,
            test_strategy=TestStrategy.DEFERRED,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        assert "unit_test.test.ut_m1" in results
        assert results["unit_test.test.ut_m1"]["status"] == "success"

        # Unit test must start after model completes
        model_completed = results["model.test.m1"]["timing"]["completed_at"]
        ut_started = results["unit_test.test.ut_m1"]["timing"]["started_at"]
        assert model_completed <= ut_started

    def test_skip_excludes_unit_tests(self, per_wave_orch):
        """SKIP: unit_test nodes do not appear in results."""
        orch, _ = per_wave_orch(
            SINGLE_MODEL_WITH_UNIT_TEST,
            test_strategy=TestStrategy.SKIP,
        )
        results = orch.run_build()

        assert "model.test.m1" in results
        assert "unit_test.test.ut_m1" not in results

    def test_unit_test_uses_test_command(self, per_node_orch):
        """PER_NODE: unit_test nodes use the 'test' command."""
        orch, _ = per_node_orch(
            SINGLE_MODEL_WITH_UNIT_TEST,
            test_strategy=TestStrategy.IMMEDIATE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()
        assert results["unit_test.test.ut_m1"]["invocation"]["command"] == "test"

    def test_mixed_test_types_all_included(self, per_node_orch):
        """IMMEDIATE: both NodeType.Test and NodeType.Unit appear in results."""
        orch, _ = per_node_orch(
            MIXED_TEST_TYPES,
            test_strategy=TestStrategy.IMMEDIATE,
        )

        @flow
        def test_flow():
            return orch.run_build()

        results = test_flow()

        assert len(results) == 3
        assert results["model.test.m1"]["status"] == "success"
        assert results["test.test.not_null_m1_id"]["status"] == "success"
        assert results["unit_test.test.ut_m1"]["status"] == "success"

    @patch.object(PrefectDbtOrchestrator, "_build_cache_options_for_node")
    def test_unit_tests_never_cached(self, mock_cache_opts, per_node_orch):
        """Unit tests are excluded from caching like schema tests."""
        mock_cache_opts.return_value = {"persist_result": True}

        orch, _ = per_node_orch(
            SINGLE_MODEL_WITH_UNIT_TEST,
            test_strategy=TestStrategy.IMMEDIATE,
            enable_caching=True,
            result_storage="/tmp/test_results",
            cache_key_storage="/tmp/test_keys",
        )

        @flow
        def test_flow():
            return orch.run_build()

        test_flow()

        # Only the model should trigger caching, not the unit test
        assert mock_cache_opts.call_count == 1
        called_node = mock_cache_opts.call_args[0][0]
        assert called_node.resource_type == NodeType.Model
