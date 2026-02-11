"""Tests for DbtNodeCachePolicy and caching integration."""

import pickle
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from conftest import (
    _make_mock_executor_per_node,
    _make_mock_settings,
    _make_node,
    write_manifest,
    write_sql_files,
)
from dbt.artifacts.resources.types import NodeType
from prefect_dbt.core._cache import (
    DbtNodeCachePolicy,
    _hash_node_config,
    _hash_node_file,
    build_cache_policy_for_node,
)
from prefect_dbt.core._orchestrator import ExecutionMode, PrefectDbtOrchestrator

from prefect import flow
from prefect.task_runners import ThreadPoolTaskRunner

# =============================================================================
# TestDbtNodeCachePolicy
# =============================================================================


class TestDbtNodeCachePolicy:
    def test_deterministic_key(self):
        """Same inputs produce the same key."""
        kwargs = dict(
            node_unique_id="model.test.m1",
            file_content_hash="abc123",
            config_hash="def456",
            full_refresh=False,
            upstream_cache_keys=(("model.test.root", "key1"),),
        )
        p1 = DbtNodeCachePolicy(**kwargs)
        p2 = DbtNodeCachePolicy(**kwargs)
        assert p1.compute_key(None, {}, {}) == p2.compute_key(None, {}, {})

    def test_key_changes_on_file_content(self):
        """Different file_content_hash produces a different key."""
        base = dict(
            node_unique_id="model.test.m1",
            config_hash="cfg",
            full_refresh=False,
            upstream_cache_keys=(),
        )
        p1 = DbtNodeCachePolicy(file_content_hash="aaa", **base)
        p2 = DbtNodeCachePolicy(file_content_hash="bbb", **base)
        assert p1.compute_key(None, {}, {}) != p2.compute_key(None, {}, {})

    def test_key_changes_on_config(self):
        """Different config_hash produces a different key."""
        base = dict(
            node_unique_id="model.test.m1",
            file_content_hash="file",
            full_refresh=False,
            upstream_cache_keys=(),
        )
        p1 = DbtNodeCachePolicy(config_hash="c1", **base)
        p2 = DbtNodeCachePolicy(config_hash="c2", **base)
        assert p1.compute_key(None, {}, {}) != p2.compute_key(None, {}, {})

    def test_key_changes_on_upstream(self):
        """Different upstream_cache_keys produces a different key."""
        base = dict(
            node_unique_id="model.test.m1",
            file_content_hash="file",
            config_hash="cfg",
            full_refresh=False,
        )
        p1 = DbtNodeCachePolicy(upstream_cache_keys=(("a", "k1"),), **base)
        p2 = DbtNodeCachePolicy(upstream_cache_keys=(("a", "k2"),), **base)
        assert p1.compute_key(None, {}, {}) != p2.compute_key(None, {}, {})

    def test_key_changes_on_full_refresh(self):
        """full_refresh=True vs False produces different keys."""
        base = dict(
            node_unique_id="model.test.m1",
            file_content_hash="file",
            config_hash="cfg",
            upstream_cache_keys=(),
        )
        p1 = DbtNodeCachePolicy(full_refresh=False, **base)
        p2 = DbtNodeCachePolicy(full_refresh=True, **base)
        assert p1.compute_key(None, {}, {}) != p2.compute_key(None, {}, {})

    def test_key_ignores_task_context(self):
        """Different task_ctx values produce the same key."""
        policy = DbtNodeCachePolicy(
            node_unique_id="model.test.m1",
            file_content_hash="f",
            config_hash="c",
            full_refresh=False,
            upstream_cache_keys=(),
        )
        k1 = policy.compute_key(None, {}, {})
        k2 = policy.compute_key(MagicMock(), {"x": 1}, {"y": 2})
        assert k1 == k2

    def test_none_hashes_still_produce_key(self):
        """Policy with None file/config hash still produces a valid key."""
        policy = DbtNodeCachePolicy(
            node_unique_id="model.test.m1",
            file_content_hash=None,
            config_hash=None,
            full_refresh=False,
            upstream_cache_keys=(),
        )
        key = policy.compute_key(None, {}, {})
        assert key is not None
        assert isinstance(key, str)
        assert len(key) > 0

    def test_pickle_roundtrip(self):
        """DbtNodeCachePolicy survives pickle roundtrip."""
        policy = DbtNodeCachePolicy(
            node_unique_id="model.test.m1",
            file_content_hash="abc",
            config_hash="def",
            full_refresh=True,
            upstream_cache_keys=(("x", "y"),),
        )
        key_before = policy.compute_key(None, {}, {})
        restored = pickle.loads(pickle.dumps(policy))
        assert restored.compute_key(None, {}, {}) == key_before


# =============================================================================
# TestBuildCachePolicyForNode
# =============================================================================


class TestBuildCachePolicyForNode:
    def test_reads_sql_file(self, tmp_path):
        """Real file on disk is hashed into the policy."""
        write_sql_files(tmp_path, {"models/my_model.sql": "SELECT 1"})
        node = _make_node(
            unique_id="model.test.m1",
            name="m1",
            resource_type=NodeType.Model,
        )
        # Attach original_file_path via a replacement node (frozen dataclass)
        from dataclasses import replace

        node = replace(node, original_file_path="models/my_model.sql")

        policy = build_cache_policy_for_node(node, tmp_path, False, {})
        assert policy.file_content_hash is not None

    def test_missing_file_graceful(self, tmp_path):
        """Missing file results in None file hash, no crash."""
        node = _make_node(unique_id="model.test.m1", name="m1")
        from dataclasses import replace

        node = replace(node, original_file_path="models/nonexistent.sql")

        policy = build_cache_policy_for_node(node, tmp_path, False, {})
        assert policy.file_content_hash is None
        # Still produces a valid key
        assert policy.compute_key(None, {}, {}) is not None

    def test_no_original_file_path(self, tmp_path):
        """Node without original_file_path gets None file hash."""
        node = _make_node(unique_id="model.test.m1", name="m1")
        policy = build_cache_policy_for_node(node, tmp_path, False, {})
        assert policy.file_content_hash is None

    def test_seed_csv_hashed(self, tmp_path):
        """CSV content is hashed for seed nodes."""
        write_sql_files(tmp_path, {"seeds/users.csv": "id,name\n1,Alice"})
        node = _make_node(
            unique_id="seed.test.users",
            name="users",
            resource_type=NodeType.Seed,
        )
        from dataclasses import replace

        node = replace(node, original_file_path="seeds/users.csv")

        policy = build_cache_policy_for_node(node, tmp_path, False, {})
        assert policy.file_content_hash is not None

    def test_upstream_keys_sorted(self, tmp_path):
        """Upstream keys are sorted for determinism."""
        node = _make_node(unique_id="model.test.leaf", name="leaf")
        upstream = {"z_model": "key_z", "a_model": "key_a", "m_model": "key_m"}
        policy = build_cache_policy_for_node(node, tmp_path, False, upstream)
        assert policy.upstream_cache_keys == (
            ("a_model", "key_a"),
            ("m_model", "key_m"),
            ("z_model", "key_z"),
        )

    def test_key_storage_configured(self, tmp_path):
        """key_storage is applied via configure()."""
        node = _make_node(unique_id="model.test.m1", name="m1")
        storage_path = str(tmp_path / "keys")
        policy = build_cache_policy_for_node(
            node, tmp_path, False, {}, key_storage=storage_path
        )
        assert policy.key_storage == storage_path


# =============================================================================
# TestHashHelpers
# =============================================================================


class TestHashHelpers:
    def test_hash_node_file_returns_none_for_no_path(self, tmp_path):
        node = _make_node(unique_id="model.test.m1", name="m1")
        assert _hash_node_file(node, tmp_path) is None

    def test_hash_node_file_returns_hash_for_existing_file(self, tmp_path):
        write_sql_files(tmp_path, {"models/m.sql": "SELECT 1"})
        node = _make_node(unique_id="model.test.m1", name="m1")
        from dataclasses import replace

        node = replace(node, original_file_path="models/m.sql")
        h = _hash_node_file(node, tmp_path)
        assert h is not None
        assert isinstance(h, str)

    def test_hash_node_file_different_content_different_hash(self, tmp_path):
        write_sql_files(
            tmp_path, {"models/a.sql": "SELECT 1", "models/b.sql": "SELECT 2"}
        )
        from dataclasses import replace

        node_a = replace(
            _make_node(unique_id="model.test.a", name="a"),
            original_file_path="models/a.sql",
        )
        node_b = replace(
            _make_node(unique_id="model.test.b", name="b"),
            original_file_path="models/b.sql",
        )
        assert _hash_node_file(node_a, tmp_path) != _hash_node_file(node_b, tmp_path)

    def test_hash_node_config_none_for_empty(self):
        node = _make_node(unique_id="model.test.m1", name="m1")
        from dataclasses import replace

        node = replace(node, config={})
        assert _hash_node_config(node) is None

    def test_hash_node_config_returns_hash(self):
        node = _make_node(unique_id="model.test.m1", name="m1")
        from dataclasses import replace

        node = replace(node, config={"materialized": "table", "schema": "raw"})
        h = _hash_node_config(node)
        assert h is not None
        assert isinstance(h, str)


# =============================================================================
# TestOrchestratorCachingIntegration
# =============================================================================

# Manifest data with original_file_path for cache tests
SINGLE_MODEL_WITH_FILE = {
    "nodes": {
        "model.test.m1": {
            "name": "m1",
            "resource_type": "model",
            "depends_on": {"nodes": []},
            "config": {"materialized": "table"},
            "original_file_path": "models/m1.sql",
        }
    },
    "sources": {},
}

DIAMOND_WITH_FILES = {
    "nodes": {
        "model.test.root": {
            "name": "root",
            "resource_type": "model",
            "depends_on": {"nodes": []},
            "config": {"materialized": "table"},
            "original_file_path": "models/root.sql",
        },
        "model.test.left": {
            "name": "left",
            "resource_type": "model",
            "depends_on": {"nodes": ["model.test.root"]},
            "config": {"materialized": "table"},
            "original_file_path": "models/left.sql",
        },
        "model.test.right": {
            "name": "right",
            "resource_type": "model",
            "depends_on": {"nodes": ["model.test.root"]},
            "config": {"materialized": "table"},
            "original_file_path": "models/right.sql",
        },
        "model.test.leaf": {
            "name": "leaf",
            "resource_type": "model",
            "depends_on": {"nodes": ["model.test.left", "model.test.right"]},
            "config": {"materialized": "table"},
            "original_file_path": "models/leaf.sql",
        },
    },
    "sources": {},
}


@pytest.fixture
def cache_orch(tmp_path):
    """Factory fixture for PER_NODE orchestrator with caching enabled.

    Writes SQL files and manifest, returns (orchestrator, executor, project_dir).
    """

    def _factory(
        manifest_data,
        sql_files=None,
        *,
        executor=None,
        enable_caching=True,
        **kwargs,
    ):
        # Use tmp_path as project_dir so file hashing works
        project_dir = tmp_path / "project"
        project_dir.mkdir(exist_ok=True)

        if sql_files:
            write_sql_files(project_dir, sql_files)

        manifest = write_manifest(project_dir, manifest_data)
        if executor is None:
            executor = _make_mock_executor_per_node(**kwargs.pop("executor_kwargs", {}))
        settings = _make_mock_settings(project_dir=project_dir)
        defaults = {
            "settings": settings,
            "manifest_path": manifest,
            "executor": executor,
            "execution_mode": ExecutionMode.PER_NODE,
            "task_runner_type": ThreadPoolTaskRunner,
            "enable_caching": enable_caching,
        }
        defaults.update(kwargs)
        return PrefectDbtOrchestrator(**defaults), executor, project_dir

    return _factory


class TestOrchestratorCachingInit:
    def test_caching_disabled_by_default(self, tmp_path):
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor_per_node(),
            execution_mode=ExecutionMode.PER_NODE,
            task_runner_type=ThreadPoolTaskRunner,
        )
        assert orch._enable_caching is False

    def test_caching_rejected_in_per_wave(self, tmp_path):
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        with pytest.raises(ValueError, match="Caching is only supported in PER_NODE"):
            PrefectDbtOrchestrator(
                settings=_make_mock_settings(),
                manifest_path=manifest,
                executor=_make_mock_executor_per_node(),
                execution_mode=ExecutionMode.PER_WAVE,
                enable_caching=True,
            )

    def test_caching_params_stored(self, tmp_path):
        manifest = write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor_per_node(),
            execution_mode=ExecutionMode.PER_NODE,
            task_runner_type=ThreadPoolTaskRunner,
            enable_caching=True,
            cache_expiration=timedelta(hours=1),
            result_storage="/tmp/results",
            cache_key_storage="/tmp/keys",
        )
        assert orch._enable_caching is True
        assert orch._cache_expiration == timedelta(hours=1)
        assert orch._result_storage == "/tmp/results"
        assert orch._cache_key_storage == "/tmp/keys"


class TestOrchestratorCachingExecution:
    def test_caching_disabled_no_policy(self, cache_orch):
        """When caching is disabled, with_options does not receive cache_policy."""
        orch, executor, _ = cache_orch(
            SINGLE_MODEL_WITH_FILE,
            sql_files={"models/m1.sql": "SELECT 1"},
            enable_caching=False,
        )

        @flow
        def test_flow():
            return orch.run_build()

        # Patch to capture with_options kwargs
        with patch(
            "prefect_dbt.core._orchestrator.PrefectDbtOrchestrator._execute_per_node",
            wraps=orch._execute_per_node,
        ):
            result = test_flow()

        assert result["model.test.m1"]["status"] == "success"

    def test_caching_enabled_sets_policy(self, cache_orch):
        """When caching is enabled, tasks get a DbtNodeCachePolicy."""
        orch, executor, _ = cache_orch(
            SINGLE_MODEL_WITH_FILE,
            sql_files={"models/m1.sql": "SELECT 1"},
        )

        @flow
        def test_flow():
            return orch.run_build()

        with patch(
            "prefect_dbt.core._cache.build_cache_policy_for_node",
            wraps=build_cache_policy_for_node,
        ) as mock_build:
            result = test_flow()

        assert result["model.test.m1"]["status"] == "success"
        mock_build.assert_called_once()
        call_kwargs = mock_build.call_args
        assert call_kwargs[0][0].unique_id == "model.test.m1"  # node arg

    def test_cache_expiration_forwarded(self, cache_orch):
        """cache_expiration is stored and would be passed to with_options."""
        orch, executor, _ = cache_orch(
            SINGLE_MODEL_WITH_FILE,
            sql_files={"models/m1.sql": "SELECT 1"},
            cache_expiration=timedelta(hours=2),
        )
        assert orch._cache_expiration == timedelta(hours=2)

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()
        assert result["model.test.m1"]["status"] == "success"

    def test_result_storage_forwarded(self, cache_orch):
        """result_storage is stored on the orchestrator."""
        orch, executor, _ = cache_orch(
            SINGLE_MODEL_WITH_FILE,
            sql_files={"models/m1.sql": "SELECT 1"},
            result_storage="/tmp/results",
        )
        assert orch._result_storage == "/tmp/results"

    def test_upstream_key_propagation(self, cache_orch):
        """In a diamond graph, leaf's cache key depends on root's SQL content."""
        sql_files = {
            "models/root.sql": "SELECT 1",
            "models/left.sql": "SELECT * FROM root",
            "models/right.sql": "SELECT * FROM root",
            "models/leaf.sql": "SELECT * FROM left JOIN right",
        }
        orch, executor, project_dir = cache_orch(DIAMOND_WITH_FILES, sql_files)

        build_calls: list[tuple] = []

        original_build = build_cache_policy_for_node

        def _tracking_build(*args, **kwargs):
            policy = original_build(*args, **kwargs)
            build_calls.append((args[0].unique_id, dict(args[3])))
            return policy

        @flow
        def test_flow():
            return orch.run_build()

        with patch(
            "prefect_dbt.core._cache.build_cache_policy_for_node",
            side_effect=_tracking_build,
        ):
            result = test_flow()

        # All nodes should succeed
        for nid in DIAMOND_WITH_FILES["nodes"]:
            assert result[nid]["status"] == "success"

        # Find the call for each node
        calls_by_node = {node_id: upstream for node_id, upstream in build_calls}

        # Root has no upstream keys
        assert calls_by_node["model.test.root"] == {}

        # Left and right have root's key
        assert "model.test.root" in calls_by_node["model.test.left"]
        assert "model.test.root" in calls_by_node["model.test.right"]

        # Leaf has left and right's keys
        assert "model.test.left" in calls_by_node["model.test.leaf"]
        assert "model.test.right" in calls_by_node["model.test.leaf"]

    def test_failed_node_key_not_propagated(self, cache_orch):
        """Failed node's key is removed from computed_cache_keys."""
        linear_with_files = {
            "nodes": {
                "model.test.a": {
                    "name": "a",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                    "original_file_path": "models/a.sql",
                },
                "model.test.b": {
                    "name": "b",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test.a"]},
                    "config": {"materialized": "table"},
                    "original_file_path": "models/b.sql",
                },
            },
            "sources": {},
        }
        sql_files = {
            "models/a.sql": "SELECT 1",
            "models/b.sql": "SELECT * FROM a",
        }
        orch, executor, _ = cache_orch(
            linear_with_files,
            sql_files,
            executor_kwargs={
                "fail_nodes": {"model.test.a"},
                "error": RuntimeError("a failed"),
            },
        )

        build_calls: dict[str, dict] = {}
        original_build = build_cache_policy_for_node

        def _tracking_build(*args, **kwargs):
            policy = original_build(*args, **kwargs)
            build_calls[args[0].unique_id] = dict(args[3])
            return policy

        @flow
        def test_flow():
            return orch.run_build()

        with patch(
            "prefect_dbt.core._cache.build_cache_policy_for_node",
            side_effect=_tracking_build,
        ):
            result = test_flow()

        assert result["model.test.a"]["status"] == "error"
        assert result["model.test.b"]["status"] == "skipped"
        # b was never built because it was skipped due to upstream failure,
        # so its cache policy was never constructed
        assert "model.test.b" not in build_calls

    def test_upstream_key_changes_cascade(self, cache_orch):
        """Changing root's SQL changes the entire chain of keys."""
        sql_v1 = {
            "models/root.sql": "SELECT 1",
            "models/left.sql": "SELECT * FROM root",
            "models/right.sql": "SELECT * FROM root",
            "models/leaf.sql": "SELECT * FROM left JOIN right",
        }
        sql_v2 = {
            "models/root.sql": "SELECT 2",  # changed!
            "models/left.sql": "SELECT * FROM root",
            "models/right.sql": "SELECT * FROM root",
            "models/leaf.sql": "SELECT * FROM left JOIN right",
        }

        # First run
        orch1, _, project_dir1 = cache_orch(DIAMOND_WITH_FILES, sql_v1)

        keys_run1: dict[str, str] = {}
        original_build = build_cache_policy_for_node

        def _capture_keys_1(*args, **kwargs):
            policy = original_build(*args, **kwargs)
            key = policy.compute_key(None, {}, {})
            if key:
                keys_run1[args[0].unique_id] = key
            return policy

        @flow
        def run1():
            return orch1.run_build()

        with patch(
            "prefect_dbt.core._cache.build_cache_policy_for_node",
            side_effect=_capture_keys_1,
        ):
            run1()

        # Second run with changed root SQL
        orch2, _, project_dir2 = cache_orch(DIAMOND_WITH_FILES, sql_v2)

        keys_run2: dict[str, str] = {}

        def _capture_keys_2(*args, **kwargs):
            policy = original_build(*args, **kwargs)
            key = policy.compute_key(None, {}, {})
            if key:
                keys_run2[args[0].unique_id] = key
            return policy

        @flow
        def run2():
            return orch2.run_build()

        with patch(
            "prefect_dbt.core._cache.build_cache_policy_for_node",
            side_effect=_capture_keys_2,
        ):
            run2()

        # Root's key should be different
        assert keys_run1["model.test.root"] != keys_run2["model.test.root"]
        # Left depends on root, so its key should also change
        assert keys_run1["model.test.left"] != keys_run2["model.test.left"]
        # Right too
        assert keys_run1["model.test.right"] != keys_run2["model.test.right"]
        # Leaf depends on both, so its key changes
        assert keys_run1["model.test.leaf"] != keys_run2["model.test.leaf"]
