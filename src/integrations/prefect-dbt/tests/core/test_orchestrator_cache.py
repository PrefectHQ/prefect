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


# =============================================================================
# TestPrecomputeAllCacheKeys
# =============================================================================


class TestPrecomputeAllCacheKeys:
    """Unit tests for _precompute_all_cache_keys()."""

    def test_linear_chain_computes_all_keys(self, tmp_path):
        """All nodes in a linear chain (a -> b -> c) get cache keys."""
        sql_files = {
            "models/a.sql": "SELECT 1",
            "models/b.sql": "SELECT * FROM a",
            "models/c.sql": "SELECT * FROM b",
        }
        write_sql_files(tmp_path, sql_files)
        manifest_data = {
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
                "model.test.c": {
                    "name": "c",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test.b"]},
                    "config": {"materialized": "table"},
                    "original_file_path": "models/c.sql",
                },
            },
            "sources": {},
        }
        manifest_path = write_manifest(tmp_path, manifest_data)
        parser = ManifestParser(manifest_path)
        all_exec = parser.get_executable_nodes()

        settings = _make_mock_settings(project_dir=tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=manifest_path,
            executor=_make_mock_executor_per_node(),
            execution_mode=ExecutionMode.PER_NODE,
            task_runner_type=ThreadPoolTaskRunner,
            enable_caching=True,
            result_storage=tmp_path / "results",
            cache_key_storage=str(tmp_path / "keys"),
        )

        keys = orch._precompute_all_cache_keys(all_exec, False, {})

        assert "model.test.a" in keys
        assert "model.test.b" in keys
        assert "model.test.c" in keys
        # All keys are non-empty strings
        for v in keys.values():
            assert isinstance(v, str) and len(v) > 0

    def test_diamond_computes_all_keys(self, tmp_path):
        """All nodes in a diamond DAG get cache keys."""
        sql_files = {
            "models/root.sql": "SELECT 1",
            "models/left.sql": "SELECT * FROM root",
            "models/right.sql": "SELECT * FROM root",
            "models/leaf.sql": "SELECT * FROM left JOIN right",
        }
        write_sql_files(tmp_path, sql_files)
        manifest_path = write_manifest(tmp_path, DIAMOND_WITH_FILES)
        parser = ManifestParser(manifest_path)
        all_exec = parser.get_executable_nodes()

        settings = _make_mock_settings(project_dir=tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=manifest_path,
            executor=_make_mock_executor_per_node(),
            execution_mode=ExecutionMode.PER_NODE,
            task_runner_type=ThreadPoolTaskRunner,
            enable_caching=True,
            result_storage=tmp_path / "results",
            cache_key_storage=str(tmp_path / "keys"),
        )

        keys = orch._precompute_all_cache_keys(all_exec, False, {})

        for node_id in DIAMOND_WITH_FILES["nodes"]:
            assert node_id in keys

    def test_keys_are_deterministic(self, tmp_path):
        """Calling _precompute_all_cache_keys twice produces identical keys."""
        sql_files = {
            "models/root.sql": "SELECT 1",
            "models/left.sql": "SELECT * FROM root",
            "models/right.sql": "SELECT * FROM root",
            "models/leaf.sql": "SELECT * FROM left JOIN right",
        }
        write_sql_files(tmp_path, sql_files)
        manifest_path = write_manifest(tmp_path, DIAMOND_WITH_FILES)
        parser = ManifestParser(manifest_path)
        all_exec = parser.get_executable_nodes()

        settings = _make_mock_settings(project_dir=tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=manifest_path,
            executor=_make_mock_executor_per_node(),
            execution_mode=ExecutionMode.PER_NODE,
            task_runner_type=ThreadPoolTaskRunner,
            enable_caching=True,
            result_storage=tmp_path / "results",
            cache_key_storage=str(tmp_path / "keys"),
        )

        keys1 = orch._precompute_all_cache_keys(all_exec, False, {})
        keys2 = orch._precompute_all_cache_keys(all_exec, False, {})

        assert keys1 == keys2

    def test_full_refresh_produces_different_keys(self, tmp_path):
        """full_refresh=True produces different keys than full_refresh=False."""
        sql_files = {"models/m1.sql": "SELECT 1"}
        write_sql_files(tmp_path, sql_files)
        manifest_path = write_manifest(tmp_path, SINGLE_MODEL_WITH_FILE)
        parser = ManifestParser(manifest_path)
        all_exec = parser.get_executable_nodes()

        settings = _make_mock_settings(project_dir=tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=manifest_path,
            executor=_make_mock_executor_per_node(),
            execution_mode=ExecutionMode.PER_NODE,
            task_runner_type=ThreadPoolTaskRunner,
            enable_caching=True,
            result_storage=tmp_path / "results",
            cache_key_storage=str(tmp_path / "keys"),
        )

        keys_normal = orch._precompute_all_cache_keys(all_exec, False, {})
        keys_refresh = orch._precompute_all_cache_keys(all_exec, True, {})

        assert keys_normal["model.test.m1"] != keys_refresh["model.test.m1"]

    def test_upstream_change_cascades(self, tmp_path):
        """Changing root SQL content changes keys for root and all downstream."""
        sql_files = {
            "models/root.sql": "SELECT 1",
            "models/left.sql": "SELECT * FROM root",
            "models/right.sql": "SELECT * FROM root",
            "models/leaf.sql": "SELECT * FROM left JOIN right",
            "models/independent.sql": "SELECT 42",
        }
        write_sql_files(tmp_path, sql_files)
        manifest_path = write_manifest(tmp_path, DIAMOND_WITH_INDEPENDENT)
        parser = ManifestParser(manifest_path)
        all_exec = parser.get_executable_nodes()

        settings = _make_mock_settings(project_dir=tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=manifest_path,
            executor=_make_mock_executor_per_node(),
            execution_mode=ExecutionMode.PER_NODE,
            task_runner_type=ThreadPoolTaskRunner,
            enable_caching=True,
            result_storage=tmp_path / "results",
            cache_key_storage=str(tmp_path / "keys"),
        )

        keys_before = orch._precompute_all_cache_keys(all_exec, False, {})

        # Modify root SQL
        (tmp_path / "models/root.sql").write_text("SELECT 2")
        keys_after = orch._precompute_all_cache_keys(all_exec, False, {})

        # Root and downstream should change
        assert keys_before["model.test.root"] != keys_after["model.test.root"]
        assert keys_before["model.test.left"] != keys_after["model.test.left"]
        assert keys_before["model.test.right"] != keys_after["model.test.right"]
        assert keys_before["model.test.leaf"] != keys_after["model.test.leaf"]
        # Independent node is unaffected
        assert (
            keys_before["model.test.independent"]
            == keys_after["model.test.independent"]
        )

    def test_source_dependencies_handled(self, tmp_path):
        """Nodes depending on sources (outside executable set) still get keys."""
        sql_files = {
            "models/stg.sql": "SELECT * FROM raw.customers",
        }
        write_sql_files(tmp_path, sql_files)
        manifest_data = {
            "nodes": {
                "model.test.stg": {
                    "name": "stg",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["source.test.raw.customers"]},
                    "config": {"materialized": "table"},
                    "original_file_path": "models/stg.sql",
                },
            },
            "sources": {
                "source.test.raw.customers": {
                    "name": "customers",
                    "resource_type": "source",
                    "fqn": ["test", "raw", "customers"],
                    "relation_name": '"main"."raw"."customers"',
                    "config": {},
                },
            },
        }
        manifest_path = write_manifest(tmp_path, manifest_data)
        parser = ManifestParser(manifest_path)
        all_exec = parser.get_executable_nodes()

        settings = _make_mock_settings(project_dir=tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=manifest_path,
            executor=_make_mock_executor_per_node(),
            execution_mode=ExecutionMode.PER_NODE,
            task_runner_type=ThreadPoolTaskRunner,
            enable_caching=True,
            result_storage=tmp_path / "results",
            cache_key_storage=str(tmp_path / "keys"),
        )

        keys = orch._precompute_all_cache_keys(all_exec, False, {})

        # Source is not in executable nodes, but stg should still get a key
        assert "model.test.stg" in keys

    def test_unreadable_file_blocks_key_and_downstream(self, tmp_path):
        """Node with original_file_path but missing file gets no key, nor do dependents."""
        # Write only leaf's file; root's file is declared but missing on disk.
        write_sql_files(tmp_path, {"models/leaf.sql": "SELECT * FROM root"})
        manifest_data = {
            "nodes": {
                "model.test.root": {
                    "name": "root",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                    "original_file_path": "models/root.sql",  # missing on disk
                },
                "model.test.leaf": {
                    "name": "leaf",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test.root"]},
                    "config": {"materialized": "table"},
                    "original_file_path": "models/leaf.sql",
                },
            },
            "sources": {},
        }
        manifest_path = write_manifest(tmp_path, manifest_data)
        parser = ManifestParser(manifest_path)
        all_exec = parser.get_executable_nodes()

        settings = _make_mock_settings(project_dir=tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=manifest_path,
            executor=_make_mock_executor_per_node(),
            execution_mode=ExecutionMode.PER_NODE,
            task_runner_type=ThreadPoolTaskRunner,
            enable_caching=True,
            result_storage=tmp_path / "results",
            cache_key_storage=str(tmp_path / "keys"),
        )

        keys = orch._precompute_all_cache_keys(all_exec, False, {})

        # root has no key because its file is unreadable
        assert "model.test.root" not in keys
        # leaf has no key because its upstream (root) has no key
        assert "model.test.leaf" not in keys

    def test_permission_denied_file_blocks_key(self, tmp_path):
        """Node whose source file exists but is unreadable gets no key."""
        write_sql_files(tmp_path, {"models/root.sql": "SELECT 1"})
        # Remove read permission
        root_file = tmp_path / "models/root.sql"
        root_file.chmod(0o000)
        try:
            manifest_data = {
                "nodes": {
                    "model.test.root": {
                        "name": "root",
                        "resource_type": "model",
                        "depends_on": {"nodes": []},
                        "config": {"materialized": "table"},
                        "original_file_path": "models/root.sql",
                    },
                },
                "sources": {},
            }
            manifest_path = write_manifest(tmp_path, manifest_data)
            parser = ManifestParser(manifest_path)
            all_exec = parser.get_executable_nodes()

            settings = _make_mock_settings(project_dir=tmp_path)
            orch = PrefectDbtOrchestrator(
                settings=settings,
                manifest_path=manifest_path,
                executor=_make_mock_executor_per_node(),
                execution_mode=ExecutionMode.PER_NODE,
                task_runner_type=ThreadPoolTaskRunner,
                enable_caching=True,
                result_storage=tmp_path / "results",
                cache_key_storage=str(tmp_path / "keys"),
            )

            keys = orch._precompute_all_cache_keys(all_exec, False, {})
            assert "model.test.root" not in keys
        finally:
            root_file.chmod(0o644)

    def test_no_original_file_path_still_gets_key(self, tmp_path):
        """Node without original_file_path (e.g. ephemeral placeholder) still gets a key."""
        manifest_data = {
            "nodes": {
                "model.test.m1": {
                    "name": "m1",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                    # no original_file_path
                },
            },
            "sources": {},
        }
        manifest_path = write_manifest(tmp_path, manifest_data)
        parser = ManifestParser(manifest_path)
        all_exec = parser.get_executable_nodes()

        settings = _make_mock_settings(project_dir=tmp_path)
        orch = PrefectDbtOrchestrator(
            settings=settings,
            manifest_path=manifest_path,
            executor=_make_mock_executor_per_node(),
            execution_mode=ExecutionMode.PER_NODE,
            task_runner_type=ThreadPoolTaskRunner,
            enable_caching=True,
            result_storage=tmp_path / "results",
            cache_key_storage=str(tmp_path / "keys"),
        )

        keys = orch._precompute_all_cache_keys(all_exec, False, {})

        # No original_file_path means no file to read — that's fine,
        # the key just won't incorporate file content.
        assert "model.test.m1" in keys


# =============================================================================
# TestCachingWithIsolatedSelection
# =============================================================================


class TestCachingWithIsolatedSelection:
    """Integration tests for caching when select= excludes upstream nodes.

    This is the core bug fix: previously, selecting a downstream node
    without its upstream dependencies (e.g. ``select="leaf"`` instead
    of ``select="+leaf"``) silently disabled caching because upstream
    cache keys were not available.  With pre-computation, cache keys
    for ALL executable nodes are computed upfront from manifest
    metadata, so caching works regardless of the select= filter.
    """

    CHAIN_WITH_FILES = {
        "nodes": {
            "model.test.root": {
                "name": "root",
                "resource_type": "model",
                "depends_on": {"nodes": []},
                "config": {"materialized": "table"},
                "original_file_path": "models/root.sql",
            },
            "model.test.mid": {
                "name": "mid",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test.root"]},
                "config": {"materialized": "table"},
                "original_file_path": "models/mid.sql",
            },
            "model.test.leaf": {
                "name": "leaf",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.test.mid"]},
                "config": {"materialized": "table"},
                "original_file_path": "models/leaf.sql",
            },
        },
        "sources": {},
    }

    SQL_FILES = {
        "models/root.sql": "SELECT 1",
        "models/mid.sql": "SELECT * FROM root",
        "models/leaf.sql": "SELECT * FROM mid",
    }

    def test_isolated_node_gets_cached_on_second_run(self, cache_orch):
        """Selecting only 'leaf' (no upstream) still enables caching."""
        from unittest.mock import patch

        orch, executor, project_dir = cache_orch(self.CHAIN_WITH_FILES, self.SQL_FILES)

        @flow
        def run_selected_twice():
            # Mock resolve_selection to return only the leaf node
            with patch(
                "prefect_dbt.core._orchestrator.resolve_selection",
                return_value={"model.test.leaf"},
            ):
                r1 = orch.run_build(select="leaf")
                r2 = orch.run_build(select="leaf")
            return r1, r2

        r1, r2 = run_selected_twice()

        # Only leaf should be in results (root and mid are not selected)
        assert "model.test.leaf" in r1
        assert "model.test.root" not in r1
        assert "model.test.mid" not in r1

        # First run executes, second run is a cache hit
        assert r1["model.test.leaf"]["status"] == "success"
        assert r2["model.test.leaf"]["status"] == "cached"
        assert executor.execute_node.call_count == 1

    def test_isolated_mid_node_gets_cached(self, cache_orch):
        """Selecting only 'mid' (upstream root not selected) still enables caching."""
        from unittest.mock import patch

        orch, executor, project_dir = cache_orch(self.CHAIN_WITH_FILES, self.SQL_FILES)

        @flow
        def run_mid_twice():
            with patch(
                "prefect_dbt.core._orchestrator.resolve_selection",
                return_value={"model.test.mid"},
            ):
                r1 = orch.run_build(select="mid")
                r2 = orch.run_build(select="mid")
            return r1, r2

        r1, r2 = run_mid_twice()

        assert r1["model.test.mid"]["status"] == "success"
        assert r2["model.test.mid"]["status"] == "cached"
        assert executor.execute_node.call_count == 1

    def test_upstream_file_change_invalidates_isolated_node(self, cache_orch):
        """Changing an unselected upstream's SQL file invalidates the selected node."""
        from unittest.mock import patch

        orch, executor, project_dir = cache_orch(self.CHAIN_WITH_FILES, self.SQL_FILES)

        @flow
        def run_then_change_upstream():
            with patch(
                "prefect_dbt.core._orchestrator.resolve_selection",
                return_value={"model.test.leaf"},
            ):
                r1 = orch.run_build(select="leaf")
                # Change root SQL — leaf's cache key should change because
                # root's key cascades through mid to leaf via pre-computation
                (project_dir / "models/root.sql").write_text("SELECT 2")
                r2 = orch.run_build(select="leaf")
            return r1, r2

        r1, r2 = run_then_change_upstream()

        assert r1["model.test.leaf"]["status"] == "success"
        # Leaf re-executes because upstream root changed
        assert r2["model.test.leaf"]["status"] == "success"
        assert executor.execute_node.call_count == 2

    def test_selective_run_does_not_poison_full_build_cache(self, cache_orch):
        """Selective run's cache entry must not be reused by a subsequent full build.

        Scenario:
        1. Full build — all nodes execute, cache populated.
        2. root.sql changes.
        3. ``select="leaf"`` — leaf re-executes (cache miss due to new
           upstream key) against OLD root/mid warehouse tables.
        4. Full build — root and mid re-execute with new data; leaf must
           also re-execute because its prior result was computed against
           stale upstream data.

        Before this fix, step 4 would cache-hit on leaf using the
        result from step 3 (computed against old warehouse data).
        """
        from unittest.mock import patch

        orch, executor, project_dir = cache_orch(self.CHAIN_WITH_FILES, self.SQL_FILES)

        @flow
        def run_scenario():
            # Step 1: full build — populate cache
            r1 = orch.run_build()

            # Step 2: change root SQL
            (project_dir / "models/root.sql").write_text("SELECT 2")

            # Step 3: selective run — only leaf
            with patch(
                "prefect_dbt.core._orchestrator.resolve_selection",
                return_value={"model.test.leaf"},
            ):
                r2 = orch.run_build(select="leaf")

            # Step 4: full build — root/mid rebuild, leaf must NOT cache-hit
            r3 = orch.run_build()
            return r1, r2, r3

        r1, r2, r3 = run_scenario()

        # Step 1: all succeed
        for nid in self.CHAIN_WITH_FILES["nodes"]:
            assert r1[nid]["status"] == "success"

        # Step 3: leaf re-executes (cache miss — upstream key changed)
        assert r2["model.test.leaf"]["status"] == "success"

        # Step 4: root/mid re-execute (new file content); leaf must also
        # re-execute (NOT cached) because its step-3 result used stale data.
        assert r3["model.test.root"]["status"] == "success"
        assert r3["model.test.mid"]["status"] == "success"
        assert r3["model.test.leaf"]["status"] == "success"

    def test_upstream_only_rebuild_invalidates_selective_cache(self, cache_orch):
        """Rebuilding upstream between two selective runs invalidates downstream cache.

        Scenario:
        1. root.sql changes.
        2. ``select=leaf`` — leaf executes against OLD root/mid tables.
        3. ``select="root mid"`` — root and mid rebuild in the warehouse.
        4. ``select=leaf`` — must NOT cache-hit from step 2 because the
           upstream warehouse data changed.

        This works because the execution state file tracks when each
        node was last executed with its current file state.  After
        step 3, the state records root and mid as current, so step 4
        uses an unsalted key (different from step 2's salted key).
        """
        from unittest.mock import patch

        orch, executor, project_dir = cache_orch(self.CHAIN_WITH_FILES, self.SQL_FILES)

        @flow
        def run_scenario():
            # Step 1: change root SQL
            (project_dir / "models/root.sql").write_text("SELECT 2")

            # Step 2: selective run — only leaf
            with patch(
                "prefect_dbt.core._orchestrator.resolve_selection",
                return_value={"model.test.leaf"},
            ):
                r1 = orch.run_build(select="leaf")

            # Step 3: selective run — only root and mid (rebuild upstream)
            with patch(
                "prefect_dbt.core._orchestrator.resolve_selection",
                return_value={"model.test.root", "model.test.mid"},
            ):
                r2 = orch.run_build(select="root mid")

            # Step 4: selective run — only leaf again
            with patch(
                "prefect_dbt.core._orchestrator.resolve_selection",
                return_value={"model.test.leaf"},
            ):
                r3 = orch.run_build(select="leaf")

            return r1, r2, r3

        r1, r2, r3 = run_scenario()

        # Step 2: leaf executes (cache miss)
        assert r1["model.test.leaf"]["status"] == "success"
        # Step 3: root and mid execute
        assert r2["model.test.root"]["status"] == "success"
        assert r2["model.test.mid"]["status"] == "success"
        # Step 4: leaf must re-execute (NOT cache-hit from step 2)
        assert r3["model.test.leaf"]["status"] == "success"

    def test_selective_execution_records_salted_key_in_state(self, cache_orch):
        """Execution state must record the actual (possibly salted) key.

        Scenario (A -> B -> C -> D chain):
        1. Run full build so all nodes have execution state.
        2. Change A's SQL.
        3. ``select=C`` — C executes with salted upstream keys because
           A and B weren't re-executed after the file change.
        4. ``select=D`` — D should NOT cache-hit because C ran against
           stale upstream data.  If the execution state incorrectly
           recorded C's unsalted precomputed key (instead of the actual
           salted key used in step 3), D would see the state as
           "current" and incorrectly reuse a stale cached result.
        """
        from unittest.mock import patch

        four_node_chain = {
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
                "model.test.c": {
                    "name": "c",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test.b"]},
                    "config": {"materialized": "table"},
                    "original_file_path": "models/c.sql",
                },
                "model.test.d": {
                    "name": "d",
                    "resource_type": "model",
                    "depends_on": {"nodes": ["model.test.c"]},
                    "config": {"materialized": "table"},
                    "original_file_path": "models/d.sql",
                },
            },
            "sources": {},
        }
        sql_files = {
            "models/a.sql": "SELECT 1",
            "models/b.sql": "SELECT * FROM a",
            "models/c.sql": "SELECT * FROM b",
            "models/d.sql": "SELECT * FROM c",
        }

        orch, executor, project_dir = cache_orch(four_node_chain, sql_files)

        @flow
        def run_scenario():
            # Step 1: full build — populates execution state for all nodes
            r1 = orch.run_build()

            # Step 2: change A's SQL
            (project_dir / "models/a.sql").write_text("SELECT 2")

            # Step 3: selective run — only C
            with patch(
                "prefect_dbt.core._orchestrator.resolve_selection",
                return_value={"model.test.c"},
            ):
                r2 = orch.run_build(select="c")

            # Step 4: selective run — only D
            with patch(
                "prefect_dbt.core._orchestrator.resolve_selection",
                return_value={"model.test.d"},
            ):
                r3 = orch.run_build(select="d")

            return r1, r2, r3

        r1, r2, r3 = run_scenario()

        # Step 1: all succeed
        assert r1["model.test.d"]["status"] == "success"
        # Step 3: C executes (salted upstream keys since A changed)
        assert r2["model.test.c"]["status"] == "success"
        # Step 4: D must re-execute, NOT cache-hit, because C was
        # built against stale upstream data.
        assert r3["model.test.d"]["status"] == "success"

    def test_failed_node_key_removed_during_execution(self, cache_orch):
        """When a node fails, its key is removed so downstream caching is disabled."""
        from unittest.mock import patch

        orch, executor, _ = cache_orch(
            self.CHAIN_WITH_FILES,
            self.SQL_FILES,
            executor_kwargs={"fail_nodes": {"model.test.mid"}},
        )

        @flow
        def run_with_failure():
            with patch(
                "prefect_dbt.core._orchestrator.resolve_selection",
                return_value={"model.test.mid", "model.test.leaf"},
            ):
                return orch.run_build(select="mid leaf")

        results = run_with_failure()

        assert results["model.test.mid"]["status"] == "error"
        # leaf is skipped due to upstream failure
        assert results["model.test.leaf"]["status"] == "skipped"
