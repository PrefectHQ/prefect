"""Tests for DbtNodeCachePolicy and caching integration."""

import pickle
from datetime import timedelta
from unittest.mock import MagicMock

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
    _hash_macro_dependencies,
    _hash_node_config,
    _hash_node_file,
    build_cache_policy_for_node,
)
from prefect_dbt.core._manifest import ManifestParser
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

    def test_key_changes_on_macro_hash(self):
        """Different macro_content_hash produces a different key."""
        base = dict(
            node_unique_id="model.test.m1",
            file_content_hash="file",
            config_hash="cfg",
            full_refresh=False,
            upstream_cache_keys=(),
        )
        p1 = DbtNodeCachePolicy(macro_content_hash="macro_a", **base)
        p2 = DbtNodeCachePolicy(macro_content_hash="macro_b", **base)
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
# TestHashMacroDependencies
# =============================================================================


class TestHashMacroDependencies:
    def test_no_macros_returns_none(self, tmp_path):
        """Node with no macro dependencies returns None."""
        node = _make_node(unique_id="model.test.m1", name="m1")
        assert _hash_macro_dependencies(node, tmp_path, {}) is None

    def test_project_macro_hashed(self, tmp_path):
        """Project-local macro file content is hashed."""
        (tmp_path / "macros").mkdir()
        (tmp_path / "macros/my_macro.sql").write_text(
            "{% macro my_macro() %}1{% endmacro %}"
        )
        node = _make_node(
            unique_id="model.test.m1",
            name="m1",
            depends_on_macros=("macro.proj.my_macro",),
        )
        macro_paths = {"macro.proj.my_macro": "macros/my_macro.sql"}
        h = _hash_macro_dependencies(node, tmp_path, macro_paths)
        assert h is not None
        assert isinstance(h, str)

    def test_different_content_different_hash(self, tmp_path):
        """Editing a macro file changes the hash."""
        (tmp_path / "macros").mkdir()
        macro_file = tmp_path / "macros/my_macro.sql"
        node = _make_node(
            unique_id="model.test.m1",
            name="m1",
            depends_on_macros=("macro.proj.my_macro",),
        )
        macro_paths = {"macro.proj.my_macro": "macros/my_macro.sql"}

        macro_file.write_text("{% macro my_macro() %}v1{% endmacro %}")
        h1 = _hash_macro_dependencies(node, tmp_path, macro_paths)

        macro_file.write_text("{% macro my_macro() %}v2{% endmacro %}")
        h2 = _hash_macro_dependencies(node, tmp_path, macro_paths)

        assert h1 != h2

    def test_external_macro_uses_id_fallback(self, tmp_path):
        """Macro with no file path falls back to macro ID."""
        node = _make_node(
            unique_id="model.test.m1",
            name="m1",
            depends_on_macros=("macro.dbt.run_query",),
        )
        macro_paths = {"macro.dbt.run_query": None}
        h = _hash_macro_dependencies(node, tmp_path, macro_paths)
        assert h is not None

    def test_unknown_macro_uses_id_fallback(self, tmp_path):
        """Macro not in macro_paths falls back to macro ID."""
        node = _make_node(
            unique_id="model.test.m1",
            name="m1",
            depends_on_macros=("macro.unknown.foo",),
        )
        h = _hash_macro_dependencies(node, tmp_path, {})
        assert h is not None


# =============================================================================
# TestManifestMacroParsing
# =============================================================================


class TestManifestMacroParsing:
    def test_depends_on_macros_parsed(self, tmp_path):
        """depends_on.macros from manifest is parsed into DbtNode."""
        manifest_data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {
                        "nodes": [],
                        "macros": ["macro.proj.my_macro", "macro.dbt.run_query"],
                    },
                    "config": {"materialized": "table"},
                }
            },
            "sources": {},
        }
        manifest_path = write_manifest(tmp_path, manifest_data)
        parser = ManifestParser(manifest_path)
        nodes = parser.get_executable_nodes()
        node = nodes["model.test.m1"]
        assert node.depends_on_macros == ("macro.proj.my_macro", "macro.dbt.run_query")

    def test_get_macro_paths(self, tmp_path):
        """ManifestParser.get_macro_paths extracts macro file paths."""
        manifest_data = {
            "nodes": {},
            "sources": {},
            "macros": {
                "macro.proj.my_macro": {
                    "name": "my_macro",
                    "original_file_path": "macros/my_macro.sql",
                },
                "macro.dbt.run_query": {
                    "name": "run_query",
                },
            },
        }
        manifest_path = write_manifest(tmp_path, manifest_data)
        parser = ManifestParser(manifest_path)
        paths = parser.get_macro_paths()
        assert paths == {
            "macro.proj.my_macro": "macros/my_macro.sql",
            "macro.dbt.run_query": None,
        }


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

DIAMOND_WITH_INDEPENDENT = {
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
        "model.test.independent": {
            "name": "independent",
            "resource_type": "model",
            "depends_on": {"nodes": []},
            "config": {"materialized": "table"},
            "original_file_path": "models/independent.sql",
        },
    },
    "sources": {},
}


@pytest.fixture
def cache_orch(tmp_path):
    """Factory fixture for PER_NODE orchestrator with caching and persistent storage.

    Creates shared result_storage and cache_key_storage directories that
    persist across calls within the same test, enabling cross-run cache tests.

    Each call gets a unique project_dir but shares storage by default.
    Returns (orchestrator, executor, project_dir).
    """
    result_dir = tmp_path / "result_storage"
    result_dir.mkdir()
    key_dir = tmp_path / "cache_key_storage"
    key_dir.mkdir()
    call_count = [0]

    def _factory(
        manifest_data,
        sql_files=None,
        *,
        executor=None,
        enable_caching=True,
        result_storage=None,
        cache_key_storage=None,
        **kwargs,
    ):
        project_dir = tmp_path / f"project_{call_count[0]}"
        project_dir.mkdir(exist_ok=True)
        call_count[0] += 1

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
            # result_storage must be a Path (not str) so Prefect creates a
            # LocalFileSystem instead of trying Block.load() on a string.
            "result_storage": result_storage or result_dir,
            "cache_key_storage": cache_key_storage or str(key_dir),
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


class TestOrchestratorCachingOutcomes:
    """Outcome-based integration tests for cross-run caching.

    These tests validate real caching behavior by running builds multiple
    times and observing whether the executor is invoked (cache miss) or
    skipped (cache hit).  No internals like ``with_options`` or
    ``build_cache_policy_for_node`` are patched or inspected.
    """

    def test_second_run_skips_unchanged_nodes(self, cache_orch):
        """Second run with identical files hits cache; executor is not invoked."""
        sql_files = {"models/m1.sql": "SELECT 1"}
        orch, executor, _ = cache_orch(SINGLE_MODEL_WITH_FILE, sql_files)

        @flow
        def run_twice():
            r1 = orch.run_build()
            r2 = orch.run_build()
            return r1, r2

        r1, r2 = run_twice()

        # First run executes; second run is a cache hit
        assert r1["model.test.m1"]["status"] == "success"
        assert r2["model.test.m1"]["status"] == "cached"
        # Executor was only called once (first run); second was a cache hit
        assert executor.execute_node.call_count == 1

    def test_cache_invalidates_downstream_on_root_change(self, cache_orch):
        """Changing root SQL invalidates downstream nodes but not independent ones."""
        sql_files = {
            "models/root.sql": "SELECT 1",
            "models/left.sql": "SELECT * FROM root",
            "models/right.sql": "SELECT * FROM root",
            "models/leaf.sql": "SELECT * FROM left JOIN right",
            "models/independent.sql": "SELECT 42",
        }
        orch, executor, project_dir = cache_orch(DIAMOND_WITH_INDEPENDENT, sql_files)

        @flow
        def run_then_change():
            r1 = orch.run_build()
            # Change root SQL to invalidate its cache key (and all downstream)
            (project_dir / "models/root.sql").write_text("SELECT 2")
            r2 = orch.run_build()
            return r1, r2

        r1, r2 = run_then_change()

        # All nodes succeed in first run
        for node_id in DIAMOND_WITH_INDEPENDENT["nodes"]:
            assert r1[node_id]["status"] == "success"
        # Second run: root changed so root + downstream re-execute,
        # independent node is a cache hit
        re_executed = {
            "model.test.root",
            "model.test.left",
            "model.test.right",
            "model.test.leaf",
        }
        for node_id in DIAMOND_WITH_INDEPENDENT["nodes"]:
            expected = "success" if node_id in re_executed else "cached"
            assert r2[node_id]["status"] == expected

        # Run 1: 5 nodes executed.
        # Run 2: 4 re-executed (root changed + downstream cascade),
        #         independent cached.
        # Total: 9
        assert executor.execute_node.call_count == 9

        # Verify independent was only executed once (cached on run 2)
        executed_nodes = [
            call.args[0].unique_id for call in executor.execute_node.call_args_list
        ]
        assert executed_nodes.count("model.test.independent") == 1

    def test_full_refresh_bypasses_cache(self, cache_orch):
        """full_refresh=True produces different cache keys, bypassing cache."""
        sql_files = {"models/m1.sql": "SELECT 1"}
        orch, executor, _ = cache_orch(SINGLE_MODEL_WITH_FILE, sql_files)

        @flow
        def run_then_refresh():
            r1 = orch.run_build()
            r2 = orch.run_build(full_refresh=True)
            return r1, r2

        r1, r2 = run_then_refresh()

        assert r1["model.test.m1"]["status"] == "success"
        assert r2["model.test.m1"]["status"] == "success"
        # Both runs execute because full_refresh changes the cache key
        assert executor.execute_node.call_count == 2

    def test_cache_persists_across_orchestrator_instances(self, cache_orch):
        """A new orchestrator instance reuses cached results from a prior run."""
        sql_files = {
            "models/root.sql": "SELECT 1",
            "models/left.sql": "SELECT * FROM root",
            "models/right.sql": "SELECT * FROM root",
            "models/leaf.sql": "SELECT * FROM left JOIN right",
        }
        orch1, exec1, _ = cache_orch(DIAMOND_WITH_FILES, sql_files)
        orch2, exec2, _ = cache_orch(DIAMOND_WITH_FILES, sql_files)

        @flow
        def run_cross_instance():
            r1 = orch1.run_build()
            r2 = orch2.run_build()
            return r1, r2

        r1, r2 = run_cross_instance()

        # First run executes; second run is all cache hits
        for node_id in DIAMOND_WITH_FILES["nodes"]:
            assert r1[node_id]["status"] == "success"
            assert r2[node_id]["status"] == "cached"

        # Instance 1 executed all nodes
        assert exec1.execute_node.call_count == 4
        # Instance 2 hit cache for all nodes
        assert exec2.execute_node.call_count == 0

    def test_full_refresh_always_executes(self, cache_orch):
        """Repeated full_refresh=True runs always execute (never cached)."""
        sql_files = {"models/m1.sql": "SELECT 1"}
        orch, executor, _ = cache_orch(SINGLE_MODEL_WITH_FILE, sql_files)

        @flow
        def run_full_refresh_twice():
            r1 = orch.run_build(full_refresh=True)
            r2 = orch.run_build(full_refresh=True)
            return r1, r2

        r1, r2 = run_full_refresh_twice()

        assert r1["model.test.m1"]["status"] == "success"
        assert r2["model.test.m1"]["status"] == "success"
        # Both runs execute — full_refresh forces re-execution
        assert executor.execute_node.call_count == 2

    def test_normal_run_after_full_refresh_uses_own_cache(self, cache_orch):
        """Normal run, full_refresh, normal again — third run hits normal cache."""
        sql_files = {"models/m1.sql": "SELECT 1"}
        orch, executor, _ = cache_orch(SINGLE_MODEL_WITH_FILE, sql_files)

        @flow
        def run_three_ways():
            r1 = orch.run_build()  # normal — cache miss
            r2 = orch.run_build(full_refresh=True)  # full_refresh — always executes
            r3 = orch.run_build()  # normal — cache hit from r1
            return r1, r2, r3

        r1, r2, r3 = run_three_ways()

        assert r1["model.test.m1"]["status"] == "success"
        assert r2["model.test.m1"]["status"] == "success"
        assert r3["model.test.m1"]["status"] == "cached"
        # r1 executes (miss), r2 executes (refresh), r3 cached (hit from r1)
        assert executor.execute_node.call_count == 2

    def test_macro_change_invalidates_cache(self, cache_orch):
        """Editing a macro file between runs invalidates the cache for dependent nodes."""
        manifest_data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {
                        "nodes": [],
                        "macros": ["macro.proj.my_macro"],
                    },
                    "config": {"materialized": "table"},
                    "original_file_path": "models/m1.sql",
                }
            },
            "sources": {},
            "macros": {
                "macro.proj.my_macro": {
                    "name": "my_macro",
                    "original_file_path": "macros/my_macro.sql",
                },
            },
        }
        sql_files = {
            "models/m1.sql": "SELECT {{ my_macro() }}",
            "macros/my_macro.sql": "{% macro my_macro() %}1{% endmacro %}",
        }
        orch, executor, project_dir = cache_orch(manifest_data, sql_files)

        @flow
        def run_then_edit_macro():
            r1 = orch.run_build()
            # Edit the macro file
            (project_dir / "macros/my_macro.sql").write_text(
                "{% macro my_macro() %}2{% endmacro %}"
            )
            r2 = orch.run_build()
            return r1, r2

        r1, r2 = run_then_edit_macro()

        assert r1["model.test.m1"]["status"] == "success"
        assert r2["model.test.m1"]["status"] == "success"
        # Both runs execute — macro content changed
        assert executor.execute_node.call_count == 2
