"""Tests for PrefectDbtOrchestrator PER_NODE mode."""

import pickle
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from conftest import (
    _make_mock_executor,
    _make_mock_executor_per_node,
    _make_mock_settings,
    write_manifest,
)
from prefect_dbt.core._executor import DbtExecutor, ExecutionResult
from prefect_dbt.core._orchestrator import (
    ExecutionMode,
    PrefectDbtOrchestrator,
    _dbt_global_log_dedupe_processor_factory,
    _DbtNodeError,
)

from prefect import flow
from prefect.task_runners import ProcessPoolTaskRunner, ThreadPoolTaskRunner

# -- Common manifest snippets ------------------------------------------------

SINGLE_MODEL = {
    "nodes": {
        "model.test.m1": {
            "name": "m1",
            "resource_type": "model",
            "depends_on": {"nodes": []},
            "config": {"materialized": "table"},
        }
    },
    "sources": {},
}

SEED_MANIFEST = {
    "nodes": {
        "seed.test.users": {
            "name": "users",
            "resource_type": "seed",
            "depends_on": {"nodes": []},
            "config": {"materialized": "seed"},
            "original_file_path": "seeds/users.csv",
        }
    },
    "sources": {},
}

SNAPSHOT_MANIFEST = {
    "nodes": {
        "snapshot.test.snap_users": {
            "name": "snap_users",
            "resource_type": "snapshot",
            "depends_on": {"nodes": []},
            "config": {"materialized": "snapshot"},
            "original_file_path": "snapshots/snap_users.sql",
        }
    },
    "sources": {},
}

INDEPENDENT_NODES = {
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
        "model.test.c": {
            "name": "c",
            "resource_type": "model",
            "depends_on": {"nodes": []},
            "config": {"materialized": "table"},
        },
    },
    "sources": {},
}

EMPTY_MANIFEST = {"nodes": {}, "sources": {}}


# -- Fixtures ----------------------------------------------------------------


@pytest.fixture
def per_node_orch(tmp_path):
    """Factory fixture for creating a PER_NODE orchestrator with mock executor.

    Returns a factory that accepts manifest data and optional overrides.
    Defaults: execution_mode=PER_NODE, task_runner_type=ThreadPoolTaskRunner,
    mock executor via _make_mock_executor_per_node().

    Usage::

        orch, executor = per_node_orch(SINGLE_MODEL)
        orch, executor = per_node_orch(data, executor_kwargs={"fail_nodes": {"model.test.a"}})
        orch, executor = per_node_orch(data, executor=custom_executor, retries=2)
    """

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
def mixed_resource_manifest_data() -> dict[str, Any]:
    """Manifest with seeds, models, and a snapshot.

    Wave 0: seed_users (seed)
    Wave 1: stg_users (model, depends on seed_users)
    Wave 1: snap_users (snapshot, depends on seed_users)
    """
    return {
        "nodes": {
            "seed.test.seed_users": {
                "name": "seed_users",
                "resource_type": "seed",
                "depends_on": {"nodes": []},
                "config": {"materialized": "seed"},
                "original_file_path": "seeds/seed_users.csv",
            },
            "model.test.stg_users": {
                "name": "stg_users",
                "resource_type": "model",
                "depends_on": {"nodes": ["seed.test.seed_users"]},
                "config": {"materialized": "view"},
                "original_file_path": "models/stg_users.sql",
            },
            "snapshot.test.snap_users": {
                "name": "snap_users",
                "resource_type": "snapshot",
                "depends_on": {"nodes": ["seed.test.seed_users"]},
                "config": {"materialized": "snapshot"},
                "original_file_path": "snapshots/snap_users.sql",
            },
        },
        "sources": {},
    }


# =============================================================================
# TestPerNodeInit
# =============================================================================


class TestPerNodeInit:
    def test_execution_mode_stored(self, tmp_path):
        manifest = write_manifest(tmp_path, EMPTY_MANIFEST)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
            execution_mode=ExecutionMode.PER_NODE,
            task_runner_type=ThreadPoolTaskRunner,
        )
        assert orch._execution_mode == ExecutionMode.PER_NODE

    def test_retries_stored(self, tmp_path):
        manifest = write_manifest(tmp_path, EMPTY_MANIFEST)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
            execution_mode=ExecutionMode.PER_NODE,
            retries=3,
            retry_delay_seconds=60,
        )
        assert orch._retries == 3
        assert orch._retry_delay_seconds == 60

    def test_int_concurrency_stored(self, tmp_path):
        manifest = write_manifest(tmp_path, EMPTY_MANIFEST)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
            concurrency=4,
        )
        assert orch._concurrency == 4

    def test_str_concurrency_stored(self, tmp_path):
        manifest = write_manifest(tmp_path, EMPTY_MANIFEST)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
            concurrency="dbt-warehouse",
        )
        assert orch._concurrency == "dbt-warehouse"

    def test_no_concurrency_default(self, tmp_path):
        manifest = write_manifest(tmp_path, EMPTY_MANIFEST)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )
        assert orch._concurrency is None

    def test_default_execution_mode_is_per_wave(self, tmp_path):
        manifest = write_manifest(tmp_path, EMPTY_MANIFEST)
        orch = PrefectDbtOrchestrator(
            settings=_make_mock_settings(),
            manifest_path=manifest,
            executor=_make_mock_executor(),
        )
        assert orch._execution_mode == ExecutionMode.PER_WAVE

    def test_invalid_execution_mode_raises(self, tmp_path):
        manifest = write_manifest(tmp_path, EMPTY_MANIFEST)
        with pytest.raises(ValueError, match="Invalid execution_mode"):
            PrefectDbtOrchestrator(
                settings=_make_mock_settings(),
                manifest_path=manifest,
                executor=_make_mock_executor(),
                execution_mode="per_nod",
            )


# =============================================================================
# TestPerNodeBasic
# =============================================================================


class TestPerNodeBasic:
    def test_empty_manifest_returns_empty_dict(self, per_node_orch):
        orch, executor = per_node_orch(EMPTY_MANIFEST)

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()
        assert result == {}
        executor.execute_node.assert_not_called()

    def test_single_node_success(self, per_node_orch):
        orch, executor = per_node_orch(SINGLE_MODEL)

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert "model.test.m1" in result
        assert result["model.test.m1"]["status"] == "success"
        executor.execute_node.assert_called_once()

    def test_multi_wave_diamond_all_succeed(self, per_node_orch, diamond_manifest_data):
        orch, executor = per_node_orch(diamond_manifest_data)

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert len(result) == 4
        for node_id in [
            "model.test.root",
            "model.test.left",
            "model.test.right",
            "model.test.leaf",
        ]:
            assert result[node_id]["status"] == "success"

        assert executor.execute_node.call_count == 4

    def test_execute_node_called_not_execute_wave(self, per_node_orch):
        """PER_NODE uses execute_node, not execute_wave."""
        orch, executor = per_node_orch(SINGLE_MODEL)

        @flow
        def test_flow():
            return orch.run_build()

        test_flow()

        executor.execute_node.assert_called_once()
        executor.execute_wave.assert_not_called()

    def test_full_refresh_forwarded(self, per_node_orch):
        orch, executor = per_node_orch(SINGLE_MODEL)

        @flow
        def test_flow():
            return orch.run_build(full_refresh=True)

        test_flow()

        args, kwargs = executor.execute_node.call_args
        assert args[2] is True or kwargs.get("full_refresh") is True

    def test_target_forwarded_to_executor(self, per_node_orch):
        orch, executor = per_node_orch(SINGLE_MODEL)

        @flow
        def test_flow():
            return orch.run_build(target="prod")

        test_flow()

        _, kwargs = executor.execute_node.call_args
        assert kwargs["target"] == "prod"

    def test_target_none_by_default(self, per_node_orch):
        orch, executor = per_node_orch(SINGLE_MODEL)

        @flow
        def test_flow():
            return orch.run_build()

        test_flow()

        _, kwargs = executor.execute_node.call_args
        assert kwargs["target"] is None

    def test_global_log_messages_emitted_across_nodes_for_in_process_runner(
        self, per_node_orch
    ):
        orch, _ = per_node_orch(
            INDEPENDENT_NODES,
            executor_kwargs={
                "log_messages": {
                    "": [("info", "Running with dbt=1.x")],
                }
            },
        )

        @flow
        def test_flow():
            return orch.run_build()

        mock_run_logger = MagicMock()
        mock_global_logger = MagicMock()
        mock_run_logger.getChild.return_value = mock_global_logger
        with patch(
            "prefect_dbt.core._orchestrator.get_run_logger",
            return_value=mock_run_logger,
        ):
            test_flow()

        global_calls = [
            call.args[0]
            for call in mock_global_logger.info.call_args_list
            if call.args and call.args[0] == "Running with dbt=1.x"
        ]
        assert len(global_calls) == 3

    def test_dbt_global_dedupe_processor_drops_duplicates(self):
        processor = _dbt_global_log_dedupe_processor_factory()
        payload_1 = {
            "flow_run_id": "flow-1",
            "task_run_id": "task-1",
            "name": "prefect.task_runs.dbt_orchestrator_global",
            "level": 20,
            "message": "Running with dbt=1.x",
        }
        payload_2 = {**payload_1, "task_run_id": "task-2"}

        assert processor("log", payload_1) == ("log", payload_1)
        assert processor("log", payload_2) is None

    def test_dbt_global_dedupe_processor_only_applies_to_target_loggers(self):
        processor = _dbt_global_log_dedupe_processor_factory()
        non_target_payload = {
            "flow_run_id": "flow-1",
            "task_run_id": "task-1",
            "name": "prefect.task_runs",
            "level": 20,
            "message": "keep me",
        }

        assert processor("log", non_target_payload) == ("log", non_target_payload)
        assert processor("log", non_target_payload) == ("log", non_target_payload)

    def test_dbt_global_dedupe_processor_lfu_retains_frequent_keys(self):
        with patch(
            "prefect_dbt.core._orchestrator._GLOBAL_LOG_DEDUPE_MAX_KEYS",
            2,
        ):
            processor = _dbt_global_log_dedupe_processor_factory()

            payload_a_1 = {
                "flow_run_id": "flow-1",
                "task_run_id": "task-1",
                "name": "prefect.task_runs.dbt_orchestrator_global",
                "level": 20,
                "message": "A",
            }
            payload_a_2 = {**payload_a_1, "task_run_id": "task-2"}
            payload_a_3 = {**payload_a_1, "task_run_id": "task-3"}
            payload_b_1 = {**payload_a_1, "message": "B"}
            payload_b_2 = {**payload_b_1, "task_run_id": "task-4"}
            payload_c_1 = {**payload_a_1, "message": "C"}

            assert processor("log", payload_a_1) == ("log", payload_a_1)
            assert processor("log", payload_a_2) is None
            assert processor("log", payload_b_1) == ("log", payload_b_1)

            # Adding C should evict B (low frequency) while retaining A (high frequency).
            assert processor("log", payload_c_1) == ("log", payload_c_1)
            assert processor("log", payload_b_2) == ("log", payload_b_2)
            assert processor("log", payload_a_3) is None

    def test_serializing_non_process_runner_does_not_capture_thread_lock(
        self, per_node_orch
    ):
        """Task closures should stay picklable for non-process runners."""

        class _SerializingThreadRunner(ThreadPoolTaskRunner):
            def submit(self, task, *args, **kwargs):
                import types
                from threading import Lock

                lock_type = type(Lock())
                to_visit = [task.fn]
                seen: set[int] = set()
                while to_visit:
                    fn = to_visit.pop()
                    if id(fn) in seen:
                        continue
                    seen.add(id(fn))
                    for cell in fn.__closure__ or ():
                        value = cell.cell_contents
                        assert not isinstance(value, lock_type)
                        if isinstance(value, types.FunctionType):
                            to_visit.append(value)
                return super().submit(task, *args, **kwargs)

        orch, _ = per_node_orch(
            SINGLE_MODEL,
            task_runner_type=_SerializingThreadRunner,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()
        assert result["model.test.m1"]["status"] == "success"

    def test_process_pool_subclass_without_processor_kw_still_runs(self, per_node_orch):
        class _SyncFuture:
            def __init__(self, result):
                self._result = result

            def result(self):
                return self._result

        class _CompatProcessPoolRunner(ProcessPoolTaskRunner):
            init_calls: list[dict[str, Any]] = []

            def __init__(self, max_workers=None):
                self.init_calls.append({"max_workers": max_workers})
                super().__init__(max_workers=max_workers)

            def __enter__(self):
                self._started = True
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                self._started = False

            def submit(self, task, parameters, wait_for=None, dependencies=None):
                return _SyncFuture(task.fn(**parameters))

        orch, _ = per_node_orch(
            SINGLE_MODEL,
            task_runner_type=_CompatProcessPoolRunner,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.m1"]["status"] == "success"
        assert _CompatProcessPoolRunner.init_calls == [{"max_workers": 1}]

    def test_process_pool_subclass_without_processor_config_api_still_runs(
        self, per_node_orch
    ):
        class _SyncFuture:
            def __init__(self, result):
                self._result = result

            def result(self):
                return self._result

        class _LegacyProcessPoolRunner(ProcessPoolTaskRunner):
            init_calls: list[dict[str, Any]] = []
            set_subprocess_message_processor_factories = None

            @property
            def subprocess_message_processor_factories(self):
                return ()

            @subprocess_message_processor_factories.setter
            def subprocess_message_processor_factories(self, value):
                raise AttributeError(
                    "Legacy runner does not support message processor configuration."
                )

            def __init__(self, max_workers=None):
                self.init_calls.append({"max_workers": max_workers})
                super().__init__(max_workers=max_workers)

            def __enter__(self):
                self._started = True
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                self._started = False

            def submit(self, task, parameters, wait_for=None, dependencies=None):
                return _SyncFuture(task.fn(**parameters))

        orch, _ = per_node_orch(
            SINGLE_MODEL,
            task_runner_type=_LegacyProcessPoolRunner,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.m1"]["status"] == "success"
        assert _LegacyProcessPoolRunner.init_calls == [{"max_workers": 1}]

    def test_process_pool_preserves_existing_subprocess_processors(self, per_node_orch):
        class _SyncFuture:
            def __init__(self, result):
                self._result = result

            def result(self):
                return self._result

        def _existing_processor_factory():
            def _processor(message_type: str, message_payload: Any):
                return message_type, message_payload

            return _processor

        class _PreconfiguredProcessPoolRunner(ProcessPoolTaskRunner):
            configured_factories: tuple[Any, ...] | None = None
            _processor_factories: tuple[Any, ...]

            @property
            def subprocess_message_processor_factories(self):
                return self._processor_factories

            @subprocess_message_processor_factories.setter
            def subprocess_message_processor_factories(self, value):
                self._processor_factories = tuple(value or ())

            def __init__(self, max_workers=None):
                super().__init__(max_workers=max_workers)
                self.subprocess_message_processor_factories = [
                    _existing_processor_factory
                ]

            def __enter__(self):
                self._started = True
                type(
                    self
                ).configured_factories = self.subprocess_message_processor_factories
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                self._started = False

            def submit(self, task, parameters, wait_for=None, dependencies=None):
                return _SyncFuture(task.fn(**parameters))

        orch, _ = per_node_orch(
            SINGLE_MODEL,
            task_runner_type=_PreconfiguredProcessPoolRunner,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.m1"]["status"] == "success"
        assert _PreconfiguredProcessPoolRunner.configured_factories == (
            _existing_processor_factory,
            _dbt_global_log_dedupe_processor_factory,
        )


# =============================================================================
# TestPerNodeCommandMapping
# =============================================================================


class TestPerNodeCommandMapping:
    def test_model_uses_run_command(self, per_node_orch):
        orch, _ = per_node_orch(SINGLE_MODEL)

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()
        assert result["model.test.m1"]["invocation"]["command"] == "run"

    def test_seed_uses_seed_command(self, per_node_orch):
        orch, _ = per_node_orch(SEED_MANIFEST)

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()
        assert result["seed.test.users"]["invocation"]["command"] == "seed"

    def test_snapshot_uses_snapshot_command(self, per_node_orch):
        orch, _ = per_node_orch(SNAPSHOT_MANIFEST)

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()
        assert result["snapshot.test.snap_users"]["invocation"]["command"] == "snapshot"

    def test_mixed_resource_types(self, per_node_orch, mixed_resource_manifest_data):
        """Each resource type gets the correct dbt command."""
        orch, _ = per_node_orch(mixed_resource_manifest_data)

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["seed.test.seed_users"]["invocation"]["command"] == "seed"
        assert result["model.test.stg_users"]["invocation"]["command"] == "run"
        assert result["snapshot.test.snap_users"]["invocation"]["command"] == "snapshot"

    def test_executor_receives_correct_command(self, per_node_orch):
        """Verify execute_node is called with the right command string."""
        orch, executor = per_node_orch(SEED_MANIFEST)

        @flow
        def test_flow():
            return orch.run_build()

        test_flow()

        args, kwargs = executor.execute_node.call_args
        assert args[1] == "seed" or kwargs.get("command") == "seed"


# =============================================================================
# TestPerNodeFailure
# =============================================================================


class TestPerNodeFailure:
    def test_failed_node_marked_as_error(self, per_node_orch):
        orch, _ = per_node_orch(
            SINGLE_MODEL,
            executor_kwargs={"success": False, "error": RuntimeError("dbt failed")},
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.m1"]["status"] == "error"
        assert "dbt failed" in result["model.test.m1"]["error"]["message"]
        assert result["model.test.m1"]["error"]["type"] == "RuntimeError"

    def test_downstream_skip_on_failure(self, per_node_orch, linear_manifest_data):
        """In a linear chain a->b->c, if a fails, b and c are skipped."""
        orch, _ = per_node_orch(
            linear_manifest_data,
            executor_kwargs={
                "fail_nodes": {"model.test.a"},
                "error": RuntimeError("a failed"),
            },
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.a"]["status"] == "error"
        assert result["model.test.b"]["status"] == "skipped"
        assert result["model.test.b"]["reason"] == "upstream failure"
        assert "model.test.a" in result["model.test.b"]["failed_upstream"]
        assert result["model.test.c"]["status"] == "skipped"

    def test_partial_wave_failure_diamond(self, per_node_orch, diamond_manifest_data):
        """In diamond graph, if 'right' fails, 'left' succeeds and 'leaf' is skipped."""
        orch, _ = per_node_orch(
            diamond_manifest_data,
            executor_kwargs={
                "fail_nodes": {"model.test.right"},
                "error": RuntimeError("right failed"),
            },
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.root"]["status"] == "success"
        assert result["model.test.left"]["status"] == "success"
        assert result["model.test.right"]["status"] == "error"
        assert result["model.test.leaf"]["status"] == "skipped"
        assert "model.test.right" in result["model.test.leaf"]["failed_upstream"]

    def test_independent_nodes_not_affected(self, per_node_orch):
        """Nodes in the same wave are independent -- failure of one doesn't affect others."""
        orch, _ = per_node_orch(
            INDEPENDENT_NODES,
            executor_kwargs={
                "fail_nodes": {"model.test.b"},
                "error": RuntimeError("b failed"),
            },
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.a"]["status"] == "success"
        assert result["model.test.b"]["status"] == "error"
        assert result["model.test.c"]["status"] == "success"

    def test_error_without_exception_no_artifacts(self, per_node_orch):
        """Node failure with no exception and no artifacts falls back to unknown error."""
        executor = MagicMock(spec=DbtExecutor)
        executor.execute_node.return_value = ExecutionResult(
            success=False, node_ids=["model.test.m1"], error=None
        )

        orch, _ = per_node_orch(SINGLE_MODEL, executor=executor)

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.m1"]["status"] == "error"
        assert result["model.test.m1"]["error"]["message"] == "unknown error"
        assert result["model.test.m1"]["error"]["type"] == "UnknownError"

    def test_error_without_exception_uses_artifact_message(self, per_node_orch):
        """Node failure with no exception extracts error from per-node artifacts."""
        executor = MagicMock(spec=DbtExecutor)
        executor.execute_node.return_value = ExecutionResult(
            success=False,
            node_ids=["model.test.m1"],
            error=None,
            artifacts={
                "model.test.m1": {
                    "status": "error",
                    "message": 'relation "raw.nonexistent_table" does not exist',
                    "execution_time": 0.5,
                }
            },
        )

        orch, _ = per_node_orch(SINGLE_MODEL, executor=executor)

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.m1"]["status"] == "error"
        assert (
            result["model.test.m1"]["error"]["message"]
            == 'relation "raw.nonexistent_table" does not exist'
        )

    def test_error_artifact_message_preferred_over_exception(self, per_node_orch):
        """Per-node artifact message takes precedence over execution-level exception."""
        executor = MagicMock(spec=DbtExecutor)
        executor.execute_node.return_value = ExecutionResult(
            success=False,
            node_ids=["model.test.m1"],
            error=RuntimeError("generic error"),
            artifacts={
                "model.test.m1": {
                    "status": "error",
                    "message": 'Database Error: relation "raw.missing" does not exist',
                    "execution_time": 0.3,
                }
            },
        )

        orch, _ = per_node_orch(SINGLE_MODEL, executor=executor)

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.m1"]["status"] == "error"
        assert (
            result["model.test.m1"]["error"]["message"]
            == 'Database Error: relation "raw.missing" does not exist'
        )
        # type still comes from the exception when present
        assert result["model.test.m1"]["error"]["type"] == "RuntimeError"

    def test_transitive_skip_propagation(self, per_node_orch, linear_manifest_data):
        """Skipped nodes also cause their dependents to be skipped."""
        orch, _ = per_node_orch(
            linear_manifest_data,
            executor_kwargs={
                "fail_nodes": {"model.test.a"},
                "error": RuntimeError("a failed"),
            },
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.a"]["status"] == "error"
        assert result["model.test.b"]["status"] == "skipped"
        assert result["model.test.c"]["status"] == "skipped"
        assert "model.test.b" in result["model.test.c"]["failed_upstream"]

    def test_executor_not_called_for_skipped_nodes(
        self, per_node_orch, linear_manifest_data
    ):
        """Skipped nodes don't invoke the executor."""
        orch, executor = per_node_orch(
            linear_manifest_data,
            executor_kwargs={
                "fail_nodes": {"model.test.a"},
                "error": RuntimeError("a failed"),
            },
        )

        @flow
        def test_flow():
            return orch.run_build()

        test_flow()

        assert executor.execute_node.call_count == 1

    def test_dbt_node_error_pickle_roundtrip(self):
        """_DbtNodeError survives pickle roundtrip across process boundaries."""
        result = ExecutionResult(
            success=False,
            node_ids=["model.test.m1"],
            error=RuntimeError("relation does not exist"),
        )
        timing = {
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_at": "2026-01-01T00:00:01+00:00",
            "duration_seconds": 1.0,
        }
        invocation = {"command": "run", "args": ["model.test.m1"]}

        err = _DbtNodeError(result, timing, invocation)
        restored = pickle.loads(pickle.dumps(err))

        assert str(restored) == str(err)
        assert restored.timing == timing
        assert restored.invocation == invocation
        assert restored.execution_result.success is False
        assert restored.execution_result.node_ids == ["model.test.m1"]
        assert str(restored.execution_result.error) == "relation does not exist"


# =============================================================================
# TestPerNodeResults
# =============================================================================


class TestPerNodeResults:
    def test_result_has_timing_fields(self, per_node_orch):
        orch, _ = per_node_orch(SINGLE_MODEL)

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()
        timing = result["model.test.m1"]["timing"]

        assert "started_at" in timing
        assert "completed_at" in timing
        assert "duration_seconds" in timing
        assert isinstance(timing["duration_seconds"], float)

    def test_result_has_per_node_invocation(self, per_node_orch):
        """PER_NODE invocation shows the specific command, not 'build'."""
        orch, _ = per_node_orch(SINGLE_MODEL)

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()
        invocation = result["model.test.m1"]["invocation"]

        assert invocation["command"] == "run"
        assert "model.test.m1" in invocation["args"]

    def test_artifacts_enrich_timing(self, per_node_orch):
        orch, _ = per_node_orch(
            SINGLE_MODEL,
            executor_kwargs={
                "artifacts": {
                    "model.test.m1": {
                        "status": "success",
                        "message": "OK",
                        "execution_time": 2.71,
                    }
                },
            },
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()
        assert result["model.test.m1"]["timing"]["execution_time"] == 2.71

    def test_failed_node_has_timing_and_invocation(self, per_node_orch):
        """Error results include timing and invocation from the last attempt."""
        orch, _ = per_node_orch(
            SINGLE_MODEL,
            executor_kwargs={"success": False, "error": RuntimeError("boom")},
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.m1"]["status"] == "error"
        assert "timing" in result["model.test.m1"]
        assert "invocation" in result["model.test.m1"]


# =============================================================================
# TestPerNodeRetries
# =============================================================================


class TestPerNodeRetries:
    def test_retry_succeeds_on_second_attempt(self, per_node_orch):
        """Node fails once, then succeeds on retry."""
        call_count = 0

        def _execute_node(
            node, command, full_refresh=False, target=None, extra_cli_args=None
        ):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ExecutionResult(
                    success=False,
                    node_ids=[node.unique_id],
                    error=RuntimeError("transient error"),
                )
            return ExecutionResult(
                success=True,
                node_ids=[node.unique_id],
            )

        executor = MagicMock(spec=DbtExecutor)
        executor.execute_node = MagicMock(side_effect=_execute_node)

        orch, _ = per_node_orch(
            SINGLE_MODEL, executor=executor, retries=1, retry_delay_seconds=0
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.m1"]["status"] == "success"
        assert executor.execute_node.call_count == 2

    def test_retries_exhausted_marks_error(self, per_node_orch):
        """Node fails after all retries and is marked as error."""
        orch, executor = per_node_orch(
            SINGLE_MODEL,
            executor_kwargs={
                "success": False,
                "error": RuntimeError("persistent error"),
            },
            retries=2,
            retry_delay_seconds=0,
        )

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert result["model.test.m1"]["status"] == "error"
        # 1 original + 2 retries = 3 calls
        assert executor.execute_node.call_count == 3


# =============================================================================
# TestPerNodeConcurrency
# =============================================================================


class TestPerNodeConcurrency:
    def test_int_concurrency_sets_max_workers(self, per_node_orch):
        """With concurrency=2, task runner is created with max_workers=2."""
        data = {
            "nodes": {
                f"model.test.m{i}": {
                    "name": f"m{i}",
                    "resource_type": "model",
                    "depends_on": {"nodes": []},
                    "config": {"materialized": "table"},
                }
                for i in range(4)
            },
            "sources": {},
        }

        captured_kwargs: list[dict] = []

        class _TrackingRunner(ThreadPoolTaskRunner):
            def __init__(self, **kwargs):
                captured_kwargs.append(kwargs)
                super().__init__(**kwargs)

        orch, _ = per_node_orch(data, task_runner_type=_TrackingRunner, concurrency=2)

        @flow
        def test_flow():
            return orch.run_build()

        result = test_flow()

        assert len(captured_kwargs) == 1
        assert captured_kwargs[0]["max_workers"] == 2

        for node_id in data["nodes"]:
            assert result[node_id]["status"] == "success"

    def test_no_concurrency_uses_wave_size(self, per_node_orch, diamond_manifest_data):
        """Without int concurrency, max_workers = max wave size."""
        captured_kwargs: list[dict] = []

        class _TrackingRunner(ThreadPoolTaskRunner):
            def __init__(self, **kwargs):
                captured_kwargs.append(kwargs)
                super().__init__(**kwargs)

        orch, _ = per_node_orch(diamond_manifest_data, task_runner_type=_TrackingRunner)

        @flow
        def test_flow():
            return orch.run_build()

        test_flow()

        # max wave size is 2 (left + right)
        assert len(captured_kwargs) == 1
        assert captured_kwargs[0]["max_workers"] == 2


# =============================================================================
# TestPerNodeTaskRunNames
# =============================================================================


class TestPerNodeTaskRunNames:
    def test_model_task_run_name(self, per_node_orch):
        """Model node gets task run name 'model m1'."""
        task_names = []

        class _CapturingRunner(ThreadPoolTaskRunner):
            def submit(self, task, *args, **kwargs):
                task_names.append(task.task_run_name)
                return super().submit(task, *args, **kwargs)

        orch, _ = per_node_orch(SINGLE_MODEL, task_runner_type=_CapturingRunner)

        @flow
        def test_flow():
            return orch.run_build()

        test_flow()
        assert "model m1" in task_names

    def test_seed_task_run_name(self, per_node_orch):
        """Seed node gets task run name 'seed users'."""
        task_names = []

        class _CapturingRunner(ThreadPoolTaskRunner):
            def submit(self, task, *args, **kwargs):
                task_names.append(task.task_run_name)
                return super().submit(task, *args, **kwargs)

        orch, _ = per_node_orch(SEED_MANIFEST, task_runner_type=_CapturingRunner)

        @flow
        def test_flow():
            return orch.run_build()

        test_flow()
        assert "seed users" in task_names

    def test_snapshot_task_run_name(self, per_node_orch):
        """Snapshot node gets task run name 'snapshot snap_users'."""
        task_names = []

        class _CapturingRunner(ThreadPoolTaskRunner):
            def submit(self, task, *args, **kwargs):
                task_names.append(task.task_run_name)
                return super().submit(task, *args, **kwargs)

        orch, _ = per_node_orch(SNAPSHOT_MANIFEST, task_runner_type=_CapturingRunner)

        @flow
        def test_flow():
            return orch.run_build()

        test_flow()
        assert "snapshot snap_users" in task_names

    def test_mixed_resource_task_run_names(
        self, per_node_orch, mixed_resource_manifest_data
    ):
        """Each resource type gets the correct '{type} {name}' task run name."""
        task_names = []

        class _CapturingRunner(ThreadPoolTaskRunner):
            def submit(self, task, *args, **kwargs):
                task_names.append(task.task_run_name)
                return super().submit(task, *args, **kwargs)

        orch, _ = per_node_orch(
            mixed_resource_manifest_data, task_runner_type=_CapturingRunner
        )

        @flow
        def test_flow():
            return orch.run_build()

        test_flow()

        assert "seed seed_users" in task_names
        assert "model stg_users" in task_names
        assert "snapshot snap_users" in task_names


# =============================================================================
# TestPerNodeWithSelectors
# =============================================================================


class TestPerNodeWithSelectors:
    @patch("prefect_dbt.core._orchestrator.resolve_selection")
    def test_select_filters_nodes(
        self, mock_resolve, per_node_orch, diamond_manifest_data
    ):
        mock_resolve.return_value = {"model.test.root", "model.test.left"}
        orch, _ = per_node_orch(diamond_manifest_data)

        @flow
        def test_flow():
            return orch.run_build(select="tag:daily")

        result = test_flow()

        assert "model.test.root" in result
        assert "model.test.left" in result
        assert "model.test.right" not in result
        assert "model.test.leaf" not in result
