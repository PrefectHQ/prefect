"""
Tests for ExecutionResult, DbtExecutor protocol, and DbtCoreExecutor.
"""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dbt.artifacts.resources.types import NodeType
from dbt_common.events.base_types import EventLevel
from prefect_dbt.core._executor import DbtCoreExecutor, DbtExecutor, ExecutionResult
from prefect_dbt.core._manifest import DbtNode

# =============================================================================
# Helpers & Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _reset_adapter_pool():
    """Reset the process-level adapter pool between tests."""
    from dbt.adapters.base.connections import BaseConnectionManager
    from dbt.adapters.base.impl import BaseAdapter
    from prefect_dbt.core._executor import _adapter_pool

    _adapter_pool.revert()
    saved_available = _adapter_pool._available
    saved_cleanup = BaseAdapter.cleanup_connections
    saved_get_if_exists = BaseConnectionManager.get_if_exists
    yield
    _adapter_pool.revert()
    _adapter_pool._available = saved_available
    BaseAdapter.cleanup_connections = saved_cleanup
    BaseConnectionManager.get_if_exists = saved_get_if_exists


def _make_node(
    unique_id: str = "model.test.my_model",
    name: str = "my_model",
    resource_type: NodeType = NodeType.Model,
) -> DbtNode:
    return DbtNode(
        unique_id=unique_id,
        name=name,
        resource_type=resource_type,
    )


def _make_settings(**overrides: object) -> MagicMock:
    """Create a mock PrefectDbtSettings."""
    settings = MagicMock()
    settings.project_dir = overrides.get("project_dir", Path("/proj"))
    settings.target_path = overrides.get("target_path", Path("target"))
    settings.log_level = overrides.get("log_level", EventLevel.DEBUG)

    @contextmanager
    def _resolve():
        yield "/tmp/profiles"

    settings.resolve_profiles_yml = _resolve
    return settings


def _mock_dbt_result(success: bool = True, results: list | None = None) -> MagicMock:
    """Create a mock dbt invocation result."""
    res = MagicMock()
    res.success = success
    res.exception = None if success else RuntimeError("dbt failed")
    if results is not None:
        res.result.results = results
    else:
        res.result = None
    return res


def _mock_node_result(
    unique_id: str,
    status: str = "success",
    message: str = "",
    execution_time: float = 1.0,
) -> MagicMock:
    nr = MagicMock()
    nr.unique_id = unique_id
    nr.status = status
    nr.message = message
    nr.execution_time = execution_time
    return nr


@pytest.fixture
def mock_dbt(monkeypatch):
    """Patch dbtRunner and return (mock_runner_cls, mock_runner) pair.

    The runner is pre-wired to return a successful result with no artifacts.
    Tests can override via `mock_runner.invoke.return_value = ...`.
    """
    mock_runner = MagicMock()
    mock_runner_cls = MagicMock(return_value=mock_runner)
    mock_runner.invoke.return_value = _mock_dbt_result(success=True)
    monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", mock_runner_cls)
    return mock_runner_cls, mock_runner


def _invoked_args(mock_runner: MagicMock) -> list[str]:
    """Extract the CLI args list from the most recent dbtRunner.invoke call."""
    return mock_runner.invoke.call_args[0][0]


# =============================================================================
# TestExecutionResult
# =============================================================================


class TestExecutionResult:
    def test_defaults(self):
        r = ExecutionResult(success=True)
        assert r.success is True
        assert r.node_ids == []
        assert r.error is None
        assert r.artifacts is None
        assert r.log_messages is None

    def test_all_fields(self):
        err = RuntimeError("boom")
        logs = {"model.a": [("info", "OK created view")]}
        r = ExecutionResult(
            success=False,
            node_ids=["model.a", "model.b"],
            error=err,
            artifacts={"model.a": {"status": "fail"}},
            log_messages=logs,
        )
        assert r.success is False
        assert r.node_ids == ["model.a", "model.b"]
        assert r.error is err
        assert "model.a" in r.artifacts
        assert r.log_messages is logs

    def test_mutable(self):
        r = ExecutionResult(success=True)
        r.success = False
        assert r.success is False


# =============================================================================
# TestDbtExecutorProtocol
# =============================================================================


class TestDbtExecutorProtocol:
    def test_dbt_core_executor_satisfies_protocol(self):
        executor = DbtCoreExecutor(_make_settings())
        assert isinstance(executor, DbtExecutor)

    def test_protocol_is_runtime_checkable(self):
        class FakeExecutor:
            def execute_node(self, node, command, full_refresh=False): ...

            def execute_wave(self, nodes, full_refresh=False): ...

            def resolve_manifest_path(self): ...

        assert isinstance(FakeExecutor(), DbtExecutor)


# =============================================================================
# TestDbtCoreExecutorInit
# =============================================================================


class TestDbtCoreExecutorInit:
    def test_defaults(self):
        settings = _make_settings()
        executor = DbtCoreExecutor(settings)
        assert executor._settings is settings
        assert executor._threads is None
        assert executor._state_path is None
        assert executor._defer is False
        assert executor._defer_state_path is None
        assert executor._favor_state is False
        assert executor._run_deps is True

    def test_full_options(self):
        settings = _make_settings()
        executor = DbtCoreExecutor(
            settings,
            threads=4,
            state_path=Path("/state"),
            defer=True,
            defer_state_path=Path("/defer-state"),
            favor_state=True,
            run_deps=False,
        )
        assert executor._threads == 4
        assert executor._state_path == Path("/state")
        assert executor._defer is True
        assert executor._defer_state_path == Path("/defer-state")
        assert executor._favor_state is True
        assert executor._run_deps is False


# =============================================================================
# TestExecuteNode
# =============================================================================


class TestExecuteNode:
    @pytest.mark.parametrize(
        "command, unique_id, name, resource_type",
        [
            ("run", "model.test.my_model", "my_model", NodeType.Model),
            ("seed", "seed.test.my_seed", "my_seed", NodeType.Seed),
            ("snapshot", "snapshot.test.my_snap", "my_snap", NodeType.Snapshot),
            ("test", "test.test.my_test", "my_test", NodeType.Test),
        ],
    )
    def test_command_types(self, mock_dbt, command, unique_id, name, resource_type):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        node = _make_node(unique_id=unique_id, name=name, resource_type=resource_type)
        result = executor.execute_node(node, command)

        assert result.success is True
        assert result.node_ids == [unique_id]
        assert result.error is None
        args = _invoked_args(mock_runner)
        assert args[0] == command
        assert name in args

    def test_full_refresh(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_node(_make_node(), "run", full_refresh=True)

        assert "--full-refresh" in _invoked_args(mock_runner)

    def test_target_forwarded(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_node(_make_node(), "run", target="prod")

        args = _invoked_args(mock_runner)
        idx = args.index("--target")
        assert args[idx + 1] == "prod"

    def test_target_absent_by_default(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_node(_make_node(), "run")

        assert "--target" not in _invoked_args(mock_runner)

    def test_full_refresh_ignored_for_test_command(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        node = _make_node(
            unique_id="test.test.t", name="t", resource_type=NodeType.Test
        )
        result = executor.execute_node(node, "test", full_refresh=True)

        assert result.success is True
        assert "--full-refresh" not in _invoked_args(mock_runner)

    def test_full_refresh_ignored_for_snapshot_command(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        node = _make_node(
            unique_id="snapshot.test.s", name="s", resource_type=NodeType.Snapshot
        )
        executor.execute_node(node, "snapshot", full_refresh=True)

        assert "--full-refresh" not in _invoked_args(mock_runner)

    def test_failure_result(self, mock_dbt):
        _, mock_runner = mock_dbt
        mock_runner.invoke.return_value = _mock_dbt_result(success=False)

        executor = DbtCoreExecutor(_make_settings())
        result = executor.execute_node(_make_node(), "run")

        assert result.success is False
        assert isinstance(result.error, RuntimeError)
        assert result.node_ids == ["model.test.my_model"]

    def test_artifacts_captured(self, mock_dbt):
        _, mock_runner = mock_dbt
        nr = _mock_node_result("model.test.my_model", "success", "OK", 2.5)
        mock_runner.invoke.return_value = _mock_dbt_result(success=True, results=[nr])

        executor = DbtCoreExecutor(_make_settings())
        result = executor.execute_node(_make_node(), "run")

        assert result.artifacts is not None
        assert "model.test.my_model" in result.artifacts
        art = result.artifacts["model.test.my_model"]
        assert art["status"] == "success"
        assert art["message"] == "OK"
        assert art["execution_time"] == 2.5

    def test_node_ids_union_of_select_and_artifacts(self, mock_dbt):
        """node_ids is the union of the select list and artifact keys."""
        _, mock_runner = mock_dbt
        nr1 = _mock_node_result("model.test.my_model")
        nr2 = _mock_node_result("test.test.attached_test")
        mock_runner.invoke.return_value = _mock_dbt_result(
            success=True, results=[nr1, nr2]
        )

        executor = DbtCoreExecutor(_make_settings())
        result = executor.execute_node(_make_node(), "run")

        # Selected node always present, plus extra from artifacts
        assert result.node_ids[0] == "model.test.my_model"
        assert "test.test.attached_test" in result.node_ids

    def test_node_ids_includes_select_even_if_missing_from_artifacts(self, mock_dbt):
        """A selected node missing from artifacts still appears in node_ids."""
        _, mock_runner = mock_dbt
        # Artifact only for an extra node, not the selected one
        nr = _mock_node_result("test.test.extra")
        mock_runner.invoke.return_value = _mock_dbt_result(success=True, results=[nr])

        executor = DbtCoreExecutor(_make_settings())
        result = executor.execute_node(_make_node(), "run")

        assert "model.test.my_model" in result.node_ids
        assert "test.test.extra" in result.node_ids

    def test_node_ids_fallback_to_select_without_artifacts(self, mock_dbt):
        """Without artifacts, node_ids falls back to the select list."""
        executor = DbtCoreExecutor(_make_settings())
        result = executor.execute_node(_make_node(), "run")

        assert result.node_ids == ["model.test.my_model"]

    def test_extract_artifacts_none_results(self, mock_dbt):
        """res.result.results being None doesn't raise."""
        _, mock_runner = mock_dbt
        res = MagicMock()
        res.success = True
        res.exception = None
        res.result.results = None
        mock_runner.invoke.return_value = res

        executor = DbtCoreExecutor(_make_settings())
        result = executor.execute_node(_make_node(), "run")

        assert result.artifacts is None

    def test_exception_during_invoke_captured(self, mock_dbt):
        mock_runner_cls, _ = mock_dbt
        mock_runner_cls.side_effect = RuntimeError("import failed")

        executor = DbtCoreExecutor(_make_settings())
        result = executor.execute_node(_make_node(), "run")

        assert result.success is False
        assert isinstance(result.error, RuntimeError)
        assert "import failed" in str(result.error)


# =============================================================================
# TestExecuteWave
# =============================================================================


class TestExecuteWave:
    def test_single_node(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        result = executor.execute_wave([_make_node()])

        assert result.success is True
        assert _invoked_args(mock_runner)[0] == "build"

    def test_multiple_nodes(self, mock_dbt):
        _, mock_runner = mock_dbt
        nr_a = _mock_node_result("model.test.a")
        nr_b = _mock_node_result("model.test.b")
        nr_c = _mock_node_result("model.test.c")
        mock_runner.invoke.return_value = _mock_dbt_result(
            success=True, results=[nr_a, nr_b, nr_c]
        )

        executor = DbtCoreExecutor(_make_settings())
        nodes = [
            _make_node("model.test.a", "a"),
            _make_node("model.test.b", "b"),
            _make_node("model.test.c", "c"),
        ]
        result = executor.execute_wave(nodes)

        assert result.success is True
        assert set(result.node_ids) == {"model.test.a", "model.test.b", "model.test.c"}
        args = _invoked_args(mock_runner)
        # CLI args contain node names (dbt selectors), not unique_ids
        assert "a" in args
        assert "b" in args
        assert "c" in args

    def test_mixed_resource_types(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        nodes = [
            _make_node("model.test.m1", "m1", NodeType.Model),
            _make_node("seed.test.s1", "s1", NodeType.Seed),
            _make_node("snapshot.test.snap1", "snap1", NodeType.Snapshot),
        ]
        result = executor.execute_wave(nodes)

        assert result.success is True
        assert _invoked_args(mock_runner)[0] == "build"

    def test_empty_raises_value_error(self):
        executor = DbtCoreExecutor(_make_settings())
        with pytest.raises(ValueError, match="Cannot execute an empty wave"):
            executor.execute_wave([])

    def test_failure_captured(self, mock_dbt):
        _, mock_runner = mock_dbt
        mock_runner.invoke.return_value = _mock_dbt_result(success=False)

        executor = DbtCoreExecutor(_make_settings())
        result = executor.execute_wave([_make_node()])

        assert result.success is False
        assert result.error is not None

    def test_full_refresh_passed_for_build(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_wave([_make_node()], full_refresh=True)

        assert "--full-refresh" in _invoked_args(mock_runner)

    def test_target_forwarded(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_wave([_make_node()], target="staging")

        args = _invoked_args(mock_runner)
        idx = args.index("--target")
        assert args[idx + 1] == "staging"

    def test_target_absent_by_default(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_wave([_make_node()])

        assert "--target" not in _invoked_args(mock_runner)

    def test_indirect_selection_forwarded(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_wave([_make_node()], indirect_selection="empty")

        args = _invoked_args(mock_runner)
        idx = args.index("--indirect-selection")
        assert args[idx + 1] == "empty"

    def test_indirect_selection_absent_by_default(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_wave([_make_node()])

        assert "--indirect-selection" not in _invoked_args(mock_runner)


# =============================================================================
# TestStateFlags
# =============================================================================


class TestStateFlags:
    def test_state_flag(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings(), state_path=Path("/my/state"))
        executor.execute_node(_make_node(), "run")

        args = _invoked_args(mock_runner)
        idx = args.index("--state")
        assert args[idx + 1] == "/my/state"

    def test_defer_flag(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings(), defer=True)
        executor.execute_node(_make_node(), "run")

        assert "--defer" in _invoked_args(mock_runner)

    def test_defer_state_flag(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings(), defer_state_path=Path("/defer"))
        executor.execute_node(_make_node(), "run")

        args = _invoked_args(mock_runner)
        idx = args.index("--defer-state")
        assert args[idx + 1] == "/defer"

    def test_favor_state_flag(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings(), favor_state=True)
        executor.execute_node(_make_node(), "run")

        assert "--favor-state" in _invoked_args(mock_runner)

    def test_combined_state_flags(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(
            _make_settings(),
            state_path=Path("/state"),
            defer=True,
            defer_state_path=Path("/defer-state"),
            favor_state=True,
        )
        executor.execute_node(_make_node(), "run")

        args = _invoked_args(mock_runner)
        assert "--state" in args
        assert "--defer" in args
        assert "--defer-state" in args
        assert "--favor-state" in args


# =============================================================================
# TestThreads
# =============================================================================


class TestThreads:
    def test_threads_present(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings(), threads=8)
        executor.execute_node(_make_node(), "run")

        args = _invoked_args(mock_runner)
        idx = args.index("--threads")
        assert args[idx + 1] == "8"

    def test_threads_absent(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_node(_make_node(), "run")

        assert "--threads" not in _invoked_args(mock_runner)


# =============================================================================
# TestCommandConstruction
# =============================================================================


class TestCommandConstruction:
    def test_project_dir(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings(project_dir=Path("/my/project")))
        executor.execute_node(_make_node(), "run")

        args = _invoked_args(mock_runner)
        idx = args.index("--project-dir")
        assert args[idx + 1] == "/my/project"

    def test_target_path(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings(target_path=Path("custom_target")))
        executor.execute_node(_make_node(), "run")

        args = _invoked_args(mock_runner)
        idx = args.index("--target-path")
        assert args[idx + 1] == "custom_target"

    def test_log_level_none(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_node(_make_node(), "run")

        args = _invoked_args(mock_runner)
        idx = args.index("--log-level")
        assert args[idx + 1] == "none"

    def test_profiles_dir_from_context_manager(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_node(_make_node(), "run")

        args = _invoked_args(mock_runner)
        idx = args.index("--profiles-dir")
        assert args[idx + 1] == "/tmp/profiles"

    def test_profiles_dir_override_context_manager(self, mock_dbt):
        _, mock_runner = mock_dbt
        settings = _make_settings()
        calls = [0]

        @contextmanager
        def _resolve():
            calls[0] += 1
            yield "/tmp/profiles"

        settings.resolve_profiles_yml = MagicMock(side_effect=_resolve)
        executor = DbtCoreExecutor(settings)

        with executor.use_resolved_profiles_dir("/stable/profiles"):
            executor.execute_node(_make_node(), "run")

        assert calls[0] == 0
        args = _invoked_args(mock_runner)
        idx = args.index("--profiles-dir")
        assert args[idx + 1] == "/stable/profiles"

    def test_fresh_runner_per_invoke(self, mock_dbt):
        """Each _invoke call creates a fresh dbtRunner instance."""
        mock_runner_cls, _ = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_node(_make_node(), "run")
        executor.execute_node(_make_node(), "run")

        assert mock_runner_cls.call_count == 2


# =============================================================================
# TestEventCapture
# =============================================================================


class TestEventCapture:
    def _make_event(self, level, msg, unique_id=None):
        """Build a minimal EventMsg-like object for callback testing."""
        event = MagicMock()
        event.info.level = level
        event.info.msg = msg
        if unique_id is not None:
            event.data.node_info.unique_id = unique_id
        else:
            del event.data.node_info
        return event

    def test_callback_registered(self, monkeypatch):
        """dbtRunner is instantiated with a callbacks list."""
        mock_runner = MagicMock()
        mock_runner.invoke.return_value = _mock_dbt_result(success=True)
        mock_cls = MagicMock(return_value=mock_runner)
        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", mock_cls)

        executor = DbtCoreExecutor(_make_settings())
        executor.execute_node(_make_node(), "run")

        call_kwargs = mock_cls.call_args[1]
        assert "callbacks" in call_kwargs
        assert len(call_kwargs["callbacks"]) == 1

    def test_log_messages_captured(self, monkeypatch):
        """Events fired during invoke are stored in result.log_messages."""
        node = _make_node()

        def _patched_cls(callbacks=None):
            cb = callbacks[0] if callbacks else None
            runner = MagicMock()

            def _invoke(args):
                cb(self._make_event(EventLevel.INFO, "1 of 3 OK", node.unique_id))
                cb(self._make_event(EventLevel.WARN, "Deprecation", None))
                return _mock_dbt_result(success=True)

            runner.invoke.side_effect = _invoke
            return runner

        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", _patched_cls)

        executor = DbtCoreExecutor(_make_settings())
        result = executor.execute_node(node, "run")

        assert result.log_messages is not None
        assert node.unique_id in result.log_messages
        assert ("info", "1 of 3 OK") in result.log_messages[node.unique_id]
        assert "" in result.log_messages
        assert ("warning", "Deprecation") in result.log_messages[""]

    def test_empty_messages_skipped(self, monkeypatch):
        """Blank or empty messages are not captured."""

        def _patched_cls(callbacks=None):
            cb = callbacks[0] if callbacks else None
            runner = MagicMock()

            def _invoke(args):
                cb(self._make_event(EventLevel.INFO, "", None))
                cb(self._make_event(EventLevel.INFO, "   ", None))
                cb(self._make_event(EventLevel.INFO, "real msg", None))
                return _mock_dbt_result(success=True)

            runner.invoke.side_effect = _invoke
            return runner

        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", _patched_cls)

        executor = DbtCoreExecutor(_make_settings())
        result = executor.execute_node(_make_node(), "run")

        assert result.log_messages is not None
        all_msgs = [m for msgs in result.log_messages.values() for _, m in msgs]
        assert "real msg" in all_msgs
        assert "" not in all_msgs
        assert "   " not in all_msgs

    def test_below_min_level_filtered(self, monkeypatch):
        """Events below settings.log_level are not captured."""

        def _patched_cls(callbacks=None):
            cb = callbacks[0] if callbacks else None
            runner = MagicMock()

            def _invoke(args):
                cb(self._make_event(EventLevel.DEBUG, "debug noise", None))
                cb(self._make_event(EventLevel.INFO, "useful info", None))
                return _mock_dbt_result(success=True)

            runner.invoke.side_effect = _invoke
            return runner

        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", _patched_cls)

        executor = DbtCoreExecutor(_make_settings(log_level=EventLevel.INFO))
        result = executor.execute_node(_make_node(), "run")

        assert result.log_messages is not None
        all_msgs = [m for msgs in result.log_messages.values() for _, m in msgs]
        assert "useful info" in all_msgs
        assert "debug noise" not in all_msgs

    def test_execute_node_keeps_global_info_logs(self, monkeypatch):
        """Per-node execution captures global INFO logs for run-level dedupe."""
        node = _make_node()

        def _patched_cls(callbacks=None):
            cb = callbacks[0] if callbacks else None
            runner = MagicMock()

            def _invoke(args):
                cb(self._make_event(EventLevel.INFO, "Running with dbt=1.x", None))
                cb(self._make_event(EventLevel.WARN, "Deprecation warning", None))
                cb(self._make_event(EventLevel.INFO, "node log", node.unique_id))
                return _mock_dbt_result(success=True)

            runner.invoke.side_effect = _invoke
            return runner

        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", _patched_cls)

        executor = DbtCoreExecutor(_make_settings())
        result = executor.execute_node(node, "run")

        assert result.log_messages is not None
        assert node.unique_id in result.log_messages
        assert ("info", "node log") in result.log_messages[node.unique_id]
        assert "" in result.log_messages
        assert ("warning", "Deprecation warning") in result.log_messages[""]
        assert ("info", "Running with dbt=1.x") in result.log_messages[""]

    def test_execute_wave_keeps_global_info_logs(self, monkeypatch):
        """Per-wave execution still captures global INFO logs."""
        node = _make_node()

        def _patched_cls(callbacks=None):
            cb = callbacks[0] if callbacks else None
            runner = MagicMock()

            def _invoke(args):
                cb(self._make_event(EventLevel.INFO, "Running with dbt=1.x", None))
                cb(self._make_event(EventLevel.INFO, "node log", node.unique_id))
                return _mock_dbt_result(success=True)

            runner.invoke.side_effect = _invoke
            return runner

        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", _patched_cls)

        executor = DbtCoreExecutor(_make_settings())
        result = executor.execute_wave([node])

        assert result.log_messages is not None
        assert "" in result.log_messages
        assert ("info", "Running with dbt=1.x") in result.log_messages[""]

    def test_no_events_yields_none(self, mock_dbt):
        """When no events are captured, log_messages is None."""
        executor = DbtCoreExecutor(_make_settings())
        result = executor.execute_node(_make_node(), "run")

        assert result.log_messages is None


# =============================================================================
# TestExtraCliArgs
# =============================================================================


class TestExtraCliArgs:
    def test_extra_cli_args_appended_execute_node(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_node(
            _make_node(),
            "run",
            extra_cli_args=["--store-failures", "--vars", "{'x': 1}"],
        )

        args = _invoked_args(mock_runner)
        assert "--store-failures" in args
        assert "--vars" in args
        assert "{'x': 1}" in args

    def test_extra_cli_args_appended_execute_wave(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_wave(
            [_make_node()],
            extra_cli_args=["--warn-error", "--no-partial-parse"],
        )

        args = _invoked_args(mock_runner)
        assert "--warn-error" in args
        assert "--no-partial-parse" in args

    def test_extra_cli_args_after_base_args(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_node(
            _make_node(),
            "run",
            extra_cli_args=["--store-failures"],
        )

        args = _invoked_args(mock_runner)
        base_end = args.index("--store-failures")
        assert args[0] == "run"
        assert "--project-dir" in args[:base_end]

    def test_extra_cli_args_none_no_effect(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_node(_make_node(), "run", extra_cli_args=None)

        args = _invoked_args(mock_runner)
        assert "--store-failures" not in args

    def test_extra_cli_args_empty_list_no_effect(self, mock_dbt):
        _, mock_runner = mock_dbt
        executor = DbtCoreExecutor(_make_settings())
        executor.execute_node(_make_node(), "run", extra_cli_args=[])

        args = _invoked_args(mock_runner)
        assert args[0] == "run"


# =============================================================================
# TestDbtCoreExecutorResolveManifestPath
# =============================================================================


class TestDbtCoreExecutorResolveManifestPath:
    def test_existing_manifest_returned(self, tmp_path):
        """When manifest.json already exists it is returned without running dbt parse."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        manifest = target_dir / "manifest.json"
        manifest.write_text("{}")

        settings = _make_settings(project_dir=tmp_path, target_path=Path("target"))
        executor = DbtCoreExecutor(settings, run_deps=False)

        result = executor.resolve_manifest_path()

        assert result == manifest.resolve()

    def test_missing_manifest_triggers_dbt_parse(self, tmp_path, monkeypatch):
        """When manifest.json is absent, dbt parse is invoked and the path returned."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        manifest_path = (target_dir / "manifest.json").resolve()

        mock_runner = MagicMock()
        mock_runner_cls = MagicMock(return_value=mock_runner)

        def _write_manifest(args):
            manifest_path.write_text("{}")
            res = MagicMock()
            res.success = True
            res.exception = None
            return res

        mock_runner.invoke.side_effect = _write_manifest
        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", mock_runner_cls)

        settings = _make_settings(project_dir=tmp_path, target_path=Path("target"))
        executor = DbtCoreExecutor(settings, run_deps=False)

        result = executor.resolve_manifest_path()

        assert result == manifest_path
        mock_runner.invoke.assert_called_once()
        call_args = mock_runner.invoke.call_args[0][0]
        assert call_args[0] == "parse"

    def test_missing_manifest_uses_profiles_override(self, tmp_path, monkeypatch):
        """Pinned profiles dir is reused for dbt parse when manifest is missing."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        manifest_path = (target_dir / "manifest.json").resolve()

        mock_runner = MagicMock()
        mock_runner_cls = MagicMock(return_value=mock_runner)

        def _write_manifest(args):
            manifest_path.write_text("{}")
            res = MagicMock()
            res.success = True
            res.exception = None
            return res

        mock_runner.invoke.side_effect = _write_manifest
        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", mock_runner_cls)

        settings = _make_settings(project_dir=tmp_path, target_path=Path("target"))
        calls = [0]

        @contextmanager
        def _resolve():
            calls[0] += 1
            yield "/tmp/profiles"

        settings.resolve_profiles_yml = MagicMock(side_effect=_resolve)
        executor = DbtCoreExecutor(settings, run_deps=False)
        with executor.use_resolved_profiles_dir("/stable/profiles"):
            result = executor.resolve_manifest_path()

        assert result == manifest_path
        assert calls[0] == 0
        call_args = mock_runner.invoke.call_args[0][0]
        idx = call_args.index("--profiles-dir")
        assert call_args[idx + 1] == "/stable/profiles"

    def test_dbt_parse_failure_raises(self, tmp_path, monkeypatch):
        """A failed dbt parse raises RuntimeError."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        mock_runner = MagicMock()
        mock_runner_cls = MagicMock(return_value=mock_runner)
        res = MagicMock()
        res.success = False
        res.exception = RuntimeError("compilation error")
        mock_runner.invoke.return_value = res
        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", mock_runner_cls)

        settings = _make_settings(project_dir=tmp_path, target_path=Path("target"))
        executor = DbtCoreExecutor(settings, run_deps=False)

        with pytest.raises(RuntimeError, match="Failed to generate manifest"):
            executor.resolve_manifest_path()

    def test_parse_succeeds_but_manifest_missing_raises(self, tmp_path, monkeypatch):
        """dbt parse succeeds but manifest still absent raises RuntimeError."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        mock_runner = MagicMock()
        mock_runner_cls = MagicMock(return_value=mock_runner)
        res = MagicMock()
        res.success = True
        res.exception = None
        mock_runner.invoke.return_value = res
        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", mock_runner_cls)

        settings = _make_settings(project_dir=tmp_path, target_path=Path("target"))
        executor = DbtCoreExecutor(settings, run_deps=False)

        with pytest.raises(RuntimeError, match="succeeded but manifest not found"):
            executor.resolve_manifest_path()

    def test_returns_absolute_path(self, tmp_path):
        """resolve_manifest_path always returns an absolute path."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "manifest.json").write_text("{}")

        settings = _make_settings(project_dir=tmp_path, target_path=Path("target"))
        executor = DbtCoreExecutor(settings, run_deps=False)

        result = executor.resolve_manifest_path()

        assert result.is_absolute()

    def test_run_parse_cli_args(self, tmp_path, monkeypatch):
        """_run_parse() passes the correct CLI args to dbt parse."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        manifest_path = (target_dir / "manifest.json").resolve()

        mock_runner = MagicMock()
        mock_runner_cls = MagicMock(return_value=mock_runner)

        def _write_manifest(args):
            manifest_path.write_text("{}")
            res = MagicMock()
            res.success = True
            res.exception = None
            return res

        mock_runner.invoke.side_effect = _write_manifest
        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", mock_runner_cls)

        settings = _make_settings(
            project_dir=tmp_path,
            target_path=Path("target"),
            log_level=EventLevel.INFO,
        )
        executor = DbtCoreExecutor(settings, run_deps=False)
        executor.resolve_manifest_path()

        # dbtRunner instantiated without callbacks (unlike _invoke)
        mock_runner_cls.assert_called_once_with()

        args = mock_runner.invoke.call_args[0][0]
        assert args[0] == "parse"
        assert "--project-dir" in args
        assert args[args.index("--project-dir") + 1] == str(tmp_path)
        assert "--profiles-dir" in args
        assert args[args.index("--profiles-dir") + 1] == "/tmp/profiles"
        assert "--target-path" in args
        assert args[args.index("--target-path") + 1] == "target"
        assert "--log-level" in args
        assert args[args.index("--log-level") + 1] == "none"
        assert "--log-level-file" in args
        assert args[args.index("--log-level-file") + 1] == str(EventLevel.INFO.value)


# =============================================================================
# TestDbtCoreExecutorRunDeps
# =============================================================================


class TestDbtCoreExecutorRunDeps:
    def test_run_deps_invokes_dbt_deps(self, monkeypatch):
        """run_deps() invokes dbt deps via dbtRunner."""
        mock_runner = MagicMock()
        mock_runner_cls = MagicMock(return_value=mock_runner)
        res = MagicMock()
        res.success = True
        res.exception = None
        mock_runner.invoke.return_value = res
        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", mock_runner_cls)

        settings = _make_settings(project_dir=Path("/proj"))
        executor = DbtCoreExecutor(settings, run_deps=False)
        executor.run_deps()

        mock_runner.invoke.assert_called_once()
        args = mock_runner.invoke.call_args[0][0]
        assert args[0] == "deps"

    def test_run_deps_cli_args(self, monkeypatch):
        """run_deps() passes the correct CLI args."""
        mock_runner = MagicMock()
        mock_runner_cls = MagicMock(return_value=mock_runner)
        res = MagicMock()
        res.success = True
        res.exception = None
        mock_runner.invoke.return_value = res
        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", mock_runner_cls)

        settings = _make_settings(
            project_dir=Path("/my/project"),
            log_level=EventLevel.INFO,
        )
        executor = DbtCoreExecutor(settings, run_deps=False)
        executor.run_deps()

        args = mock_runner.invoke.call_args[0][0]
        assert args[0] == "deps"
        assert "--project-dir" in args
        assert args[args.index("--project-dir") + 1] == "/my/project"
        assert "--profiles-dir" in args
        assert args[args.index("--profiles-dir") + 1] == "/tmp/profiles"
        assert "--log-level" in args
        assert args[args.index("--log-level") + 1] == "none"
        assert "--log-level-file" in args
        assert args[args.index("--log-level-file") + 1] == str(EventLevel.INFO.value)
        # dbt deps does NOT accept --target-path
        assert "--target-path" not in args

    def test_run_deps_uses_profiles_override(self, monkeypatch):
        """Pinned profiles dir is reused for dbt deps."""
        mock_runner = MagicMock()
        mock_runner_cls = MagicMock(return_value=mock_runner)
        res = MagicMock()
        res.success = True
        res.exception = None
        mock_runner.invoke.return_value = res
        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", mock_runner_cls)

        settings = _make_settings()
        calls = [0]

        @contextmanager
        def _resolve():
            calls[0] += 1
            yield "/tmp/profiles"

        settings.resolve_profiles_yml = MagicMock(side_effect=_resolve)
        executor = DbtCoreExecutor(settings, run_deps=False)
        with executor.use_resolved_profiles_dir("/stable/profiles"):
            executor.run_deps()

        # resolve_profiles_yml should NOT have been called (override active)
        assert calls[0] == 0
        args = mock_runner.invoke.call_args[0][0]
        idx = args.index("--profiles-dir")
        assert args[idx + 1] == "/stable/profiles"

    def test_run_deps_failure_raises(self, monkeypatch):
        """A failed dbt deps raises RuntimeError."""
        mock_runner = MagicMock()
        mock_runner_cls = MagicMock(return_value=mock_runner)
        res = MagicMock()
        res.success = False
        res.exception = RuntimeError("package download failed")
        mock_runner.invoke.return_value = res
        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", mock_runner_cls)

        settings = _make_settings()
        executor = DbtCoreExecutor(settings, run_deps=False)

        with pytest.raises(RuntimeError, match="Failed to install packages"):
            executor.run_deps()

    def test_run_deps_fresh_runner(self, monkeypatch):
        """run_deps() creates a fresh dbtRunner (no callbacks)."""
        mock_runner = MagicMock()
        mock_runner_cls = MagicMock(return_value=mock_runner)
        res = MagicMock()
        res.success = True
        res.exception = None
        mock_runner.invoke.return_value = res
        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", mock_runner_cls)

        settings = _make_settings()
        executor = DbtCoreExecutor(settings, run_deps=False)
        executor.run_deps()

        # dbtRunner instantiated without callbacks (like _run_parse)
        mock_runner_cls.assert_called_once_with()

    def test_resolve_manifest_path_calls_run_deps_when_manifest_missing(
        self, tmp_path, monkeypatch
    ):
        """run_deps() is called before dbt parse when manifest is missing."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        manifest_path = target_dir / "manifest.json"

        call_order: list[str] = []

        mock_runner = MagicMock()
        mock_runner_cls = MagicMock(return_value=mock_runner)

        def _fake_invoke(args):
            call_order.append(args[0])
            # Write manifest when parse is called so the method succeeds
            if args[0] == "parse":
                manifest_path.write_text("{}")
            res = MagicMock()
            res.success = True
            res.exception = None
            return res

        mock_runner.invoke.side_effect = _fake_invoke
        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", mock_runner_cls)

        settings = _make_settings(project_dir=tmp_path, target_path=Path("target"))
        executor = DbtCoreExecutor(settings)  # run_deps=True by default
        executor.resolve_manifest_path()

        # deps runs before parse
        assert call_order == ["deps", "parse"]

    def test_resolve_manifest_path_skips_run_deps_when_manifest_exists(
        self, tmp_path, monkeypatch
    ):
        """run_deps() is NOT called when manifest already exists on disk."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "manifest.json").write_text("{}")

        mock_runner = MagicMock()
        mock_runner_cls = MagicMock(return_value=mock_runner)
        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", mock_runner_cls)

        settings = _make_settings(project_dir=tmp_path, target_path=Path("target"))
        executor = DbtCoreExecutor(settings)  # run_deps=True by default
        executor.resolve_manifest_path()

        # dbtRunner should NOT have been called — manifest exists
        mock_runner_cls.assert_not_called()

    def test_resolve_manifest_path_skips_run_deps_when_false(
        self, tmp_path, monkeypatch
    ):
        """run_deps() is NOT called when run_deps=False even if manifest is missing."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        manifest_path = target_dir / "manifest.json"

        mock_runner = MagicMock()
        mock_runner_cls = MagicMock(return_value=mock_runner)

        def _fake_invoke(args):
            # Only parse should be called, not deps
            manifest_path.write_text("{}")
            res = MagicMock()
            res.success = True
            res.exception = None
            return res

        mock_runner.invoke.side_effect = _fake_invoke
        monkeypatch.setattr("prefect_dbt.core._executor.dbtRunner", mock_runner_cls)

        settings = _make_settings(project_dir=tmp_path, target_path=Path("target"))
        executor = DbtCoreExecutor(settings, run_deps=False)
        executor.resolve_manifest_path()

        # Only one invocation (parse), no deps
        mock_runner.invoke.assert_called_once()
        args = mock_runner.invoke.call_args[0][0]
        assert args[0] == "parse"


# =============================================================================
# TestAdapterPool
# =============================================================================


class TestAdapterPool:
    """Tests for _AdapterPool state machine."""

    def test_unavailable_when_import_fails(self):
        """Pool is unavailable when dbt adapter imports fail."""
        with patch.dict("sys.modules", {"dbt.adapters.factory": None}):
            from prefect_dbt.core._executor import _AdapterPool

            pool = _AdapterPool()
        assert not pool.available

    def test_get_runner_returns_fresh_runner_when_inactive(self):
        """In INACTIVE state, get_runner returns a new dbtRunner."""
        from prefect_dbt.core._executor import _AdapterPool

        pool = _AdapterPool()
        runner, pooled = pool.get_runner(callbacks=[])
        assert runner is not None
        assert pooled is False

    def test_transitions_to_pooled_after_success(self):
        """After on_success, state transitions to POOLED."""
        from prefect_dbt.core._executor import _AdapterPool, _PoolState

        pool = _AdapterPool()
        if not pool.available:
            pytest.skip("dbt adapter imports not available")
        pool.activate()
        runner, pooled = pool.get_runner(callbacks=[])
        pool.on_success()
        assert pool._state == _PoolState.POOLED

    def test_pooled_runner_is_reused(self):
        """In POOLED state, get_runner returns the cached runner."""
        from prefect_dbt.core._executor import _AdapterPool

        pool = _AdapterPool()
        if not pool.available:
            pytest.skip("dbt adapter imports not available")
        pool.activate()
        runner1, _ = pool.get_runner(callbacks=[])
        pool.on_success()
        runner2, pooled = pool.get_runner(callbacks=[])
        assert pooled is True
        assert runner2 is runner1

    def test_revert_goes_to_inactive(self):
        """revert() transitions back to INACTIVE."""
        from prefect_dbt.core._executor import _AdapterPool, _PoolState

        pool = _AdapterPool()
        if not pool.available:
            pytest.skip("dbt adapter imports not available")
        pool.activate()
        pool.get_runner(callbacks=[])
        pool.on_success()
        pool.revert()
        assert pool._state == _PoolState.INACTIVE

    def test_revert_restores_original_adapter_management(self):
        """revert() restores the original adapter_management function."""
        import dbt.adapters.factory as factory_mod
        from prefect_dbt.core._executor import _AdapterPool

        original = factory_mod.adapter_management
        pool = _AdapterPool()
        if not pool.available:
            pytest.skip("dbt adapter imports not available")
        pool.activate()
        pool.get_runner(callbacks=[])
        pool.revert()
        assert factory_mod.adapter_management is original

    def test_activate_suppresses_cleanup_connections(self):
        """activate() patches BaseAdapter.cleanup_connections to a no-op."""
        from dbt.adapters.base.impl import BaseAdapter
        from prefect_dbt.core._executor import _AdapterPool

        original_cleanup = BaseAdapter.cleanup_connections
        pool = _AdapterPool()
        if not pool.available:
            pytest.skip("dbt adapter imports not available")
        pool.activate()
        assert BaseAdapter.cleanup_connections is not original_cleanup
        # The patched method should be a no-op (callable with an adapter)
        BaseAdapter.cleanup_connections(MagicMock())  # should not raise

    def test_revert_restores_cleanup_connections(self):
        """revert() restores BaseAdapter.cleanup_connections."""
        from dbt.adapters.base.impl import BaseAdapter
        from prefect_dbt.core._executor import _AdapterPool

        original_cleanup = BaseAdapter.cleanup_connections
        pool = _AdapterPool()
        if not pool.available:
            pytest.skip("dbt adapter imports not available")
        pool.activate()
        pool.revert()
        assert BaseAdapter.cleanup_connections is original_cleanup

    def test_cleanup_restores_cleanup_connections(self):
        """_cleanup() restores BaseAdapter.cleanup_connections."""
        from dbt.adapters.base.impl import BaseAdapter
        from prefect_dbt.core._executor import _AdapterPool

        original_cleanup = BaseAdapter.cleanup_connections
        pool = _AdapterPool()
        if not pool.available:
            pytest.skip("dbt adapter imports not available")
        pool.activate()
        pool._cleanup()
        assert BaseAdapter.cleanup_connections is original_cleanup

    def test_activate_patches_get_if_exists(self):
        """activate() patches get_if_exists for connection transplant."""
        from dbt.adapters.base.connections import BaseConnectionManager
        from prefect_dbt.core._executor import _AdapterPool

        original = BaseConnectionManager.get_if_exists
        pool = _AdapterPool()
        if not pool.available:
            pytest.skip("dbt adapter imports not available")
        pool.activate()
        assert BaseConnectionManager.get_if_exists is not original

    def test_revert_restores_get_if_exists(self):
        """revert() restores original get_if_exists."""
        from dbt.adapters.base.connections import BaseConnectionManager
        from prefect_dbt.core._executor import _AdapterPool

        original = BaseConnectionManager.get_if_exists
        pool = _AdapterPool()
        if not pool.available:
            pytest.skip("dbt adapter imports not available")
        pool.activate()
        pool.revert()
        assert BaseConnectionManager.get_if_exists is original

    def test_get_if_exists_transplants_open_connection(self):
        """Patched get_if_exists moves an open conn to the new thread key."""
        from dbt.adapters.base.connections import BaseConnectionManager
        from prefect_dbt.core._executor import _AdapterPool

        pool = _AdapterPool()
        if not pool.available:
            pytest.skip("dbt adapter imports not available")
        pool.activate()

        # Simulate a connection manager with an open connection under old key
        conn_mgr = MagicMock(spec=BaseConnectionManager)
        conn_mgr.get_thread_identifier.return_value = (1, 999)  # new thread
        old_conn = MagicMock()
        old_conn.state = "open"
        conn_mgr.thread_connections = {(1, 100): old_conn}
        conn_mgr.lock = __import__("threading").RLock()

        result = BaseConnectionManager.get_if_exists(conn_mgr)
        assert result is old_conn
        # Old key removed, new key set
        assert (1, 100) not in conn_mgr.thread_connections
        assert conn_mgr.thread_connections[(1, 999)] is old_conn

    def test_get_if_exists_skips_non_open_connections(self):
        """Patched get_if_exists only transplants connections with state='open'."""
        from dbt.adapters.base.connections import BaseConnectionManager
        from prefect_dbt.core._executor import _AdapterPool

        pool = _AdapterPool()
        if not pool.available:
            pytest.skip("dbt adapter imports not available")
        pool.activate()

        conn_mgr = MagicMock(spec=BaseConnectionManager)
        conn_mgr.get_thread_identifier.return_value = (1, 999)
        closed_conn = MagicMock()
        closed_conn.state = "closed"
        conn_mgr.thread_connections = {(1, 100): closed_conn}
        conn_mgr.lock = __import__("threading").RLock()

        result = BaseConnectionManager.get_if_exists(conn_mgr)
        assert result is None
        # Closed connection not transplanted
        assert (1, 100) in conn_mgr.thread_connections


# =============================================================================
# TestAdapterPoolIntegration
# =============================================================================


class TestAdapterPoolIntegration:
    """Tests for _AdapterPool integration with DbtCoreExecutor._invoke."""

    def test_invoke_activates_pool_on_first_call(self):
        """_invoke should activate the adapter pool before calling dbtRunner."""
        from prefect_dbt.core._executor import _adapter_pool, _PoolState

        mock_result = _mock_dbt_result(success=True)

        with patch("prefect_dbt.core._executor.dbtRunner") as MockRunner:
            MockRunner.return_value.invoke.return_value = mock_result
            MockRunner.return_value.callbacks = []

            executor = DbtCoreExecutor(settings=_make_settings(), pool_adapters=True)
            node = _make_node()

            executor.execute_node(node, "run")

            # Pool should have been activated
            assert _adapter_pool._state in (_PoolState.FIRST_CALL, _PoolState.POOLED)

    def test_invoke_reverts_pool_on_failure(self):
        """On invoke failure in pooled mode, pool reverts to INACTIVE."""
        from prefect_dbt.core._executor import _adapter_pool, _PoolState

        mock_result = _mock_dbt_result(success=False)
        mock_result.exception = RuntimeError("connection lost")

        with patch("prefect_dbt.core._executor.dbtRunner") as MockRunner:
            MockRunner.return_value.invoke.return_value = mock_result
            MockRunner.return_value.callbacks = []

            executor = DbtCoreExecutor(settings=_make_settings(), pool_adapters=True)
            node = _make_node()

            # Force into POOLED state
            _adapter_pool._state = _PoolState.POOLED
            _adapter_pool._runner = MockRunner.return_value

            result = executor.execute_node(node, "run")

            assert not result.success
            assert _adapter_pool._state == _PoolState.INACTIVE

    def test_invoke_works_without_pool(self):
        """When pool_adapters is False (default), pooling is not used."""
        from prefect_dbt.core._executor import _adapter_pool, _PoolState

        mock_result = _mock_dbt_result(success=True)

        with patch("prefect_dbt.core._executor.dbtRunner") as MockRunner:
            MockRunner.return_value.invoke.return_value = mock_result

            executor = DbtCoreExecutor(settings=_make_settings())
            node = _make_node()
            result = executor.execute_node(node, "run")

            assert result.success
            assert _adapter_pool._state == _PoolState.INACTIVE
            MockRunner.assert_called_once()


# =============================================================================
# TestAdapterPoolEdgeCases
# =============================================================================


class TestAdapterPoolEdgeCases:
    """Edge cases for adapter pool behavior."""

    def test_activate_is_idempotent(self):
        """Calling activate() multiple times doesn't break state."""
        from prefect_dbt.core._executor import _adapter_pool, _PoolState

        _adapter_pool.activate()
        _adapter_pool.activate()  # second call should be a no-op
        assert _adapter_pool._state == _PoolState.FIRST_CALL

    def test_revert_when_already_inactive_is_safe(self):
        """revert() on INACTIVE state doesn't raise."""
        from prefect_dbt.core._executor import _adapter_pool, _PoolState

        assert _adapter_pool._state == _PoolState.INACTIVE
        _adapter_pool.revert()  # should not raise
        assert _adapter_pool._state == _PoolState.INACTIVE

    def test_pool_unavailable_skips_all_operations(self):
        """When imports failed, all pool operations are no-ops."""
        from prefect_dbt.core._executor import _AdapterPool, _PoolState

        pool = _AdapterPool.__new__(_AdapterPool)
        pool._state = _PoolState.INACTIVE
        pool._available = False
        pool._runner = None
        pool._original_adapter_management = None
        pool._original_base_cleanup = None
        pool._original_get_if_exists = None
        pool._cleanup_registered = False

        pool.activate()  # no-op
        assert pool._state == _PoolState.INACTIVE

        runner, pooled = pool.get_runner(callbacks=[])
        assert not pooled
        assert runner is not None

    def test_on_success_only_transitions_from_first_call(self):
        """on_success() is a no-op when not in FIRST_CALL state."""
        from prefect_dbt.core._executor import _adapter_pool, _PoolState

        assert _adapter_pool._state == _PoolState.INACTIVE
        _adapter_pool.on_success()  # should not raise or change state
        assert _adapter_pool._state == _PoolState.INACTIVE

    def test_cleanup_is_safe_after_revert(self):
        """_cleanup() after revert doesn't double-close connections."""
        from prefect_dbt.core._executor import _adapter_pool

        _adapter_pool.activate()
        _adapter_pool.revert()
        _adapter_pool._cleanup()  # should not raise
