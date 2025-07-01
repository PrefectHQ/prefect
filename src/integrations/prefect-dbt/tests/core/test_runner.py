"""
Unit tests for PrefectDbtRunner - focusing on outcomes.
"""

from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from dbt.artifacts.resources.types import NodeType
from dbt.artifacts.schemas.results import RunStatus
from dbt.artifacts.schemas.run import RunExecutionResult
from dbt.contracts.graph.manifest import Manifest
from dbt.contracts.graph.nodes import ManifestNode
from dbt_common.events.base_types import EventLevel, EventMsg
from prefect_dbt.core.runner import PrefectDbtRunner, execute_dbt_node
from prefect_dbt.core.settings import PrefectDbtSettings


@pytest.fixture
def mock_dbt_runner_instance():
    """Fixture providing a mock dbt runner instance."""
    mock_instance = Mock()
    mock_instance.invoke.return_value = Mock(success=True, exception=None)
    return mock_instance


@pytest.fixture
def mock_dbt_runner_class(mock_dbt_runner_instance, monkeypatch):
    """Fixture providing a mock dbt runner class."""
    mock_class = Mock(return_value=mock_dbt_runner_instance)
    monkeypatch.setattr("prefect_dbt.core.runner.dbtRunner", mock_class)
    return mock_class


@pytest.fixture
def mock_settings():
    """Fixture providing a mock settings object with resolve_profiles_yml method."""
    mock_settings = Mock()
    mock_settings.resolve_profiles_yml.return_value.__enter__ = Mock(
        return_value="/mock/profiles/dir"
    )
    mock_settings.resolve_profiles_yml.return_value.__exit__ = Mock(return_value=None)
    return mock_settings


@pytest.fixture
def mock_log_level():
    """Fixture providing a mock log level with value attribute."""
    mock_log_level = Mock()
    mock_log_level.value = "info"
    return mock_log_level


@pytest.fixture
def mock_runner_with_common_mocks(monkeypatch, mock_settings, mock_log_level):
    """Fixture providing a runner with common mocks applied."""
    runner = PrefectDbtRunner()

    # Mock the callback methods
    monkeypatch.setattr(runner, "_create_logging_callback", Mock())
    monkeypatch.setattr(runner, "_create_node_started_callback", Mock())
    monkeypatch.setattr(runner, "_create_node_finished_callback", Mock())

    # Mock the log_level property
    monkeypatch.setattr(
        PrefectDbtRunner, "log_level", property(lambda self: mock_log_level)
    )

    # Set mock settings
    runner.settings = mock_settings

    return runner


@pytest.fixture
def mock_manifest_node():
    """Fixture providing a mock manifest node."""
    mock_node = Mock(spec=ManifestNode)
    mock_node.resource_type = NodeType.Model
    mock_node.unique_id = "test_node"
    mock_node.relation_name = "test_relation"
    mock_node.name = "test_model"
    mock_node.description = "Test model"
    mock_node.config = Mock()
    mock_node.config.meta = {}
    return mock_node


@pytest.fixture
def mock_manifest():
    """Fixture providing a mock manifest."""
    mock_manifest = Mock(spec=Manifest)
    mock_manifest.metadata = Mock()
    mock_manifest.metadata.adapter_type = "snowflake"
    mock_manifest.nodes = {}
    return mock_manifest


@pytest.fixture
def mock_successful_result():
    """Fixture providing a mock successful dbt result."""
    mock_result = Mock()
    mock_result.success = True
    mock_result.exception = None
    return mock_result


@pytest.fixture
def mock_dbt_runner_with_success(mock_successful_result):
    """Fixture providing a mock dbt runner instance that returns successful results."""
    mock_instance = Mock()
    mock_instance.invoke.return_value = mock_successful_result
    return mock_instance


@pytest.fixture
def mock_dbt_runner_class_with_success(mock_dbt_runner_with_success, monkeypatch):
    """Fixture providing a mock dbt runner class that returns successful results."""
    mock_class = Mock(return_value=mock_dbt_runner_with_success)
    monkeypatch.setattr("prefect_dbt.core.runner.dbtRunner", mock_class)
    return mock_class


@pytest.fixture
def mock_runner_with_all_mocks(
    monkeypatch, mock_settings, mock_log_level, mock_dbt_runner_class_with_success
):
    """Fixture providing a runner with all common mocks applied."""
    runner = PrefectDbtRunner()

    # Mock the callback methods
    monkeypatch.setattr(runner, "_create_logging_callback", Mock())
    monkeypatch.setattr(runner, "_create_node_started_callback", Mock())
    monkeypatch.setattr(runner, "_create_node_finished_callback", Mock())

    # Mock the log_level property
    monkeypatch.setattr(
        PrefectDbtRunner, "log_level", property(lambda self: mock_log_level)
    )

    # Set mock settings
    runner.settings = mock_settings

    return runner


@pytest.fixture
def mock_context_manager():
    """Fixture providing a mock context manager for hydrated_context."""
    mock_context = Mock()
    mock_context.__enter__ = Mock()
    mock_context.__exit__ = Mock()
    return mock_context


@pytest.fixture
def mock_context_manager_with_patch(monkeypatch, mock_context_manager):
    """Fixture providing a mock context manager with monkeypatch applied."""
    monkeypatch.setattr(
        "prefect_dbt.core._tracker.hydrated_context",
        Mock(return_value=mock_context_manager),
    )
    return mock_context_manager


@pytest.fixture
def mock_failed_result():
    """Fixture providing a mock failed dbt result."""
    mock_result = Mock()
    mock_result.success = False
    mock_result.exception = "Test exception"
    return mock_result


@pytest.fixture
def mock_dbt_runner_with_failure(mock_failed_result):
    """Fixture providing a mock dbt runner instance that returns failed results."""
    mock_instance = Mock()
    mock_instance.invoke.return_value = mock_failed_result
    return mock_instance


@pytest.fixture
def mock_dbt_runner_class_with_failure(mock_dbt_runner_with_failure, monkeypatch):
    """Fixture providing a mock dbt runner class that returns failed results."""
    mock_class = Mock(return_value=mock_dbt_runner_with_failure)
    monkeypatch.setattr("prefect_dbt.core.runner.dbtRunner", mock_class)
    return mock_class


@pytest.fixture
def mock_runner_with_callback_mocks(monkeypatch, mock_settings, mock_log_level):
    """Fixture providing a runner with callback mocks applied."""
    runner = PrefectDbtRunner()

    # Mock the callback methods
    mock_logging_callback = Mock()
    mock_node_started_callback = Mock()
    mock_node_finished_callback = Mock()
    monkeypatch.setattr(
        runner, "_create_logging_callback", Mock(return_value=mock_logging_callback)
    )
    monkeypatch.setattr(
        runner,
        "_create_node_started_callback",
        Mock(return_value=mock_node_started_callback),
    )
    monkeypatch.setattr(
        runner,
        "_create_node_finished_callback",
        Mock(return_value=mock_node_finished_callback),
    )

    # Mock the log_level property
    monkeypatch.setattr(
        PrefectDbtRunner, "log_level", property(lambda self: mock_log_level)
    )

    # Set mock settings
    runner.settings = mock_settings

    return (
        runner,
        mock_logging_callback,
        mock_node_started_callback,
        mock_node_finished_callback,
    )


@pytest.fixture
def mock_runner_with_force_nodes_as_tasks(monkeypatch, mock_settings, mock_log_level):
    """Fixture providing a runner with _force_nodes_as_tasks=True and common mocks."""
    runner = PrefectDbtRunner(_force_nodes_as_tasks=True)

    # Mock the callback methods
    mock_logging_callback = Mock()
    mock_node_started_callback = Mock()
    mock_node_finished_callback = Mock()
    monkeypatch.setattr(
        runner, "_create_logging_callback", Mock(return_value=mock_logging_callback)
    )
    monkeypatch.setattr(
        runner,
        "_create_node_started_callback",
        Mock(return_value=mock_node_started_callback),
    )
    monkeypatch.setattr(
        runner,
        "_create_node_finished_callback",
        Mock(return_value=mock_node_finished_callback),
    )

    # Mock the log_level property
    monkeypatch.setattr(
        PrefectDbtRunner, "log_level", property(lambda self: mock_log_level)
    )

    # Set mock settings
    runner.settings = mock_settings

    return (
        runner,
        mock_logging_callback,
        mock_node_started_callback,
        mock_node_finished_callback,
    )


@pytest.fixture
def mock_flow_context(monkeypatch):
    """Fixture providing a mock flow context."""
    context = {"flow_run_context": {"foo": "bar"}}
    monkeypatch.setattr(
        "prefect_dbt.core.runner.serialize_context",
        Mock(return_value=context),
    )
    return context


@pytest.fixture
def mock_task_context(monkeypatch):
    """Fixture providing a mock task context."""
    context = {"task_run_context": {"foo": "bar"}}
    monkeypatch.setattr(
        "prefect_dbt.core.runner.serialize_context",
        Mock(return_value=context),
    )
    return context


@pytest.fixture
def mock_empty_context(monkeypatch):
    """Fixture providing a mock empty context."""
    context = {}
    monkeypatch.setattr(
        "prefect_dbt.core.runner.serialize_context",
        Mock(return_value=context),
    )
    return context


@pytest.fixture
def mock_project():
    """Fixture providing a mock project."""
    mock_project = Mock()
    mock_project.project_name = "test_project"
    return mock_project


@pytest.fixture
def mock_file_operations(monkeypatch):
    """Fixture providing mock file operations."""
    mock_open = Mock()
    mock_open.return_value.__enter__ = Mock(return_value=Mock())
    mock_open.return_value.__exit__ = Mock(return_value=None)
    monkeypatch.setattr("builtins.open", mock_open)
    return mock_open


class TestPrefectDbtRunner:
    """Test cases focusing on PrefectDbtRunner outcomes and behavior."""

    def test_runner_initializes_with_working_configuration(self):
        """Test that runner initializes with a working configuration."""
        runner = PrefectDbtRunner()

        # Verify runner has all required components
        assert runner.settings is not None
        assert isinstance(runner.settings, PrefectDbtSettings)
        assert runner.raise_on_failure is True
        assert runner.client is not None
        assert runner._force_nodes_as_tasks is False

    def test_runner_accepts_custom_configuration(self):
        """Test that runner accepts and uses custom configuration."""
        custom_settings = PrefectDbtSettings()
        custom_manifest = Mock(spec=Manifest)
        custom_client = Mock()

        runner = PrefectDbtRunner(
            manifest=custom_manifest,
            settings=custom_settings,
            raise_on_failure=False,
            client=custom_client,
            include_compiled_code=True,
            _force_nodes_as_tasks=True,
        )

        # Verify custom configuration is used
        assert runner.settings == custom_settings
        assert runner.raise_on_failure is False
        assert runner.client == custom_client
        assert runner.include_compiled_code is True
        assert runner._force_nodes_as_tasks is True

    def test_runner_handles_manifest_loading_successfully(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that runner can load manifest successfully."""
        mock_manifest = Mock(spec=Manifest)

        # Mock file operations
        mock_open = Mock()
        mock_open.return_value.__enter__ = Mock(return_value=Mock())
        mock_open.return_value.__exit__ = Mock(return_value=None)

        monkeypatch.setattr("builtins.open", mock_open)
        monkeypatch.setattr("json.load", Mock(return_value={"test": "data"}))
        monkeypatch.setattr(Manifest, "from_dict", Mock(return_value=mock_manifest))

        runner = PrefectDbtRunner()
        runner._target_path = Path("target")
        runner._project_dir = Path("/test/project")

        # Access manifest property to trigger loading
        result = runner.manifest

        assert result == mock_manifest

    def test_runner_handles_manifest_file_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that runner handles missing manifest file gracefully."""
        monkeypatch.setattr("builtins.open", Mock(side_effect=FileNotFoundError()))

        runner = PrefectDbtRunner()
        runner._target_path = Path("target")
        runner._project_dir = Path("/test/project")

        with pytest.raises(ValueError, match="Manifest file not found"):
            _ = runner.manifest

    def test_runner_processes_dbt_events_correctly(self):
        """Test that runner processes dbt events correctly."""
        event = Mock(spec=EventMsg)
        event.info = Mock()
        event.info.msg = "Test dbt event message"

        result = PrefectDbtRunner.get_dbt_event_msg(event)
        assert result == "Test dbt event message"

    def test_runner_extracts_node_id_from_events(self):
        """Test that runner extracts node IDs from dbt events."""
        runner = PrefectDbtRunner()

        event = Mock(spec=EventMsg)
        event.data = Mock()
        event.data.node_info = Mock()
        event.data.node_info.unique_id = "test_node_id"

        result = runner._get_dbt_event_node_id(event)
        assert result == "test_node_id"

    def test_runner_handles_cli_argument_parsing(self):
        """Test that runner handles CLI argument parsing correctly."""
        runner = PrefectDbtRunner()

        # Test extracting flag values
        args = ["--target-path", "/custom/path", "run"]
        result_args, value = runner._extract_flag_value(args, "--target-path")

        assert result_args == ["run"]
        assert value == "/custom/path"

        # Test handling missing flags
        args = ["run"]
        result_args, value = runner._extract_flag_value(args, "--target-path")

        assert result_args == ["run"]
        assert value is None

    def test_runner_updates_settings_from_kwargs(self):
        """Test that runner updates settings from kwargs."""
        runner = PrefectDbtRunner()
        kwargs = {"target_path": "/custom/path"}

        runner._update_setting_from_kwargs("target_path", kwargs)

        assert runner._target_path == "/custom/path"
        assert "target_path" not in kwargs  # Should be removed

    def test_runner_updates_settings_from_cli_flags(self):
        """Test that runner updates settings from CLI flags."""
        runner = PrefectDbtRunner()
        args = ["--target-path", "/custom/path", "run"]

        result_args = runner._update_setting_from_cli_flag(
            args, "--target-path", "target_path", Path
        )

        assert result_args == ["run"]
        assert runner._target_path == Path("/custom/path")

    def test_runner_invokes_dbt_successfully(
        self,
        mock_runner_with_all_mocks,
        mock_dbt_runner_class_with_success,
        monkeypatch,
    ):
        """Test that runner invokes dbt commands successfully."""
        runner = mock_runner_with_all_mocks

        # Mock context to simulate no flow/task run
        monkeypatch.setattr(
            "prefect_dbt.core.runner.serialize_context", Mock(return_value={})
        )

        result = runner.invoke(["run"])

        assert result.success is True
        assert result.exception is None
        mock_dbt_runner_class_with_success.return_value.invoke.assert_called_once()
        # No assertion about callbacks in invoke call; callbacks are passed to dbtRunner constructor only.

    def test_runner_invokes_dbt_with_callbacks_in_flow_context(
        self,
        mock_runner_with_callback_mocks,
        mock_dbt_runner_class_with_success,
        mock_flow_context,
    ):
        """Test that runner adds callbacks when in flow context."""
        (
            runner,
            mock_logging_callback,
            mock_node_started_callback,
            mock_node_finished_callback,
        ) = mock_runner_with_callback_mocks

        result = runner.invoke(["run"])

        assert result.success is True
        assert result.exception is None
        mock_dbt_runner_class_with_success.return_value.invoke.assert_called_once()
        # Verify callbacks are added when in flow context
        mock_dbt_runner_class_with_success.assert_called_once_with(
            callbacks=[
                mock_logging_callback,
                mock_node_started_callback,
                mock_node_finished_callback,
            ]
        )

    def test_runner_invokes_dbt_with_callbacks_in_task_context(
        self,
        mock_runner_with_callback_mocks,
        mock_dbt_runner_class_with_success,
        mock_task_context,
    ):
        """Test that runner adds callbacks when in task context."""
        (
            runner,
            mock_logging_callback,
            mock_node_started_callback,
            mock_node_finished_callback,
        ) = mock_runner_with_callback_mocks

        result = runner.invoke(["run"])

        assert result.success is True
        assert result.exception is None
        mock_dbt_runner_class_with_success.return_value.invoke.assert_called_once()
        # Verify callbacks are added when in task context
        mock_dbt_runner_class_with_success.assert_called_once_with(
            callbacks=[
                mock_logging_callback,
                mock_node_started_callback,
                mock_node_finished_callback,
            ]
        )
        call_kwargs = mock_dbt_runner_class_with_success.return_value.invoke.call_args[
            1
        ]
        assert call_kwargs["log_level"] == "none"
        assert call_kwargs["log_level_file"] == "info"

    def test_runner_invokes_dbt_with_force_nodes_as_tasks(
        self,
        mock_runner_with_force_nodes_as_tasks,
        mock_dbt_runner_class_with_success,
        mock_empty_context,
    ):
        """Test that runner adds callbacks when force_nodes_as_tasks is True."""
        (
            runner,
            mock_logging_callback,
            mock_node_started_callback,
            mock_node_finished_callback,
        ) = mock_runner_with_force_nodes_as_tasks

        result = runner.invoke(["run"])

        assert result.success is True
        assert result.exception is None
        mock_dbt_runner_class_with_success.return_value.invoke.assert_called_once()
        # Verify callbacks are added when _force_nodes_as_tasks is True
        mock_dbt_runner_class_with_success.assert_called_once_with(
            callbacks=[
                mock_logging_callback,
                mock_node_started_callback,
                mock_node_finished_callback,
            ]
        )

    def test_runner_sets_log_level_none_in_flow_context(
        self,
        mock_runner_with_all_mocks,
        mock_dbt_runner_class_with_success,
        monkeypatch,
    ):
        """Test that runner sets log_level to 'none' when in flow context."""
        runner = mock_runner_with_all_mocks

        # Mock context to simulate flow run (non-empty dict)
        monkeypatch.setattr(
            "prefect_dbt.core.runner.serialize_context",
            Mock(return_value={"flow_run_context": {"foo": "bar"}}),
        )

        result = runner.invoke(["run"])

        assert result.success is True
        assert result.exception is None
        mock_dbt_runner_class_with_success.return_value.invoke.assert_called_once()
        # Verify log_level is set to 'none' and log_level_file uses the original level as string
        call_kwargs = mock_dbt_runner_class_with_success.return_value.invoke.call_args[
            1
        ]
        assert call_kwargs["log_level"] == "none"
        assert call_kwargs["log_level_file"] == "info"

    def test_runner_sets_log_level_none_in_task_context(
        self,
        mock_runner_with_callback_mocks,
        mock_dbt_runner_class_with_success,
        mock_task_context,
    ):
        """Test that runner sets log_level to 'none' when in task context."""
        runner, _, _, _ = mock_runner_with_callback_mocks

        result = runner.invoke(["run"])

        assert result.success is True
        assert result.exception is None
        mock_dbt_runner_class_with_success.return_value.invoke.assert_called_once()
        # Verify log_level is set to 'none' and log_level_file uses the original level as string
        call_kwargs = mock_dbt_runner_class_with_success.return_value.invoke.call_args[
            1
        ]
        assert call_kwargs["log_level"] == "none"
        assert call_kwargs["log_level_file"] == "info"

    def test_runner_uses_original_log_level_outside_context(
        self,
        mock_runner_with_callback_mocks,
        mock_dbt_runner_class_with_success,
        mock_empty_context,
    ):
        """Test that runner uses original log_level when not in flow/task context."""
        runner, _, _, _ = mock_runner_with_callback_mocks

        result = runner.invoke(["run"])

        assert result.success is True
        assert result.exception is None
        mock_dbt_runner_class_with_success.return_value.invoke.assert_called_once()
        # Verify log_level uses the original level when not in context
        call_kwargs = mock_dbt_runner_class_with_success.return_value.invoke.call_args[
            1
        ]
        assert call_kwargs["log_level"] == "info"
        assert call_kwargs["log_level_file"] == "info"

    def test_runner_uses_original_log_level_with_force_nodes_as_tasks(
        self,
        mock_runner_with_force_nodes_as_tasks,
        mock_dbt_runner_class_with_success,
        mock_empty_context,
    ):
        """Test that runner uses original log_level when force_nodes_as_tasks is True but not in context."""
        runner, _, _, _ = mock_runner_with_force_nodes_as_tasks

        result = runner.invoke(["run"])

        assert result.success is True
        assert result.exception is None
        mock_dbt_runner_class_with_success.return_value.invoke.assert_called_once()
        # Verify log_level uses the original level even with _force_nodes_as_tasks
        call_kwargs = mock_dbt_runner_class_with_success.return_value.invoke.call_args[
            1
        ]
        assert call_kwargs["log_level"] == "info"
        assert call_kwargs["log_level_file"] == "info"

    def test_runner_force_nodes_as_tasks_with_flow_context(
        self,
        mock_runner_with_force_nodes_as_tasks,
        mock_dbt_runner_class_with_success,
        mock_flow_context,
    ):
        """Test that runner behavior when _force_nodes_as_tasks is True and in flow context."""
        (
            runner,
            mock_logging_callback,
            mock_node_started_callback,
            mock_node_finished_callback,
        ) = mock_runner_with_force_nodes_as_tasks

        result = runner.invoke(["run"])

        assert result.success is True
        assert result.exception is None
        mock_dbt_runner_class_with_success.return_value.invoke.assert_called_once()
        # Verify callbacks are added and log_level is 'none' when in flow context
        mock_dbt_runner_class_with_success.assert_called_once_with(
            callbacks=[
                mock_logging_callback,
                mock_node_started_callback,
                mock_node_finished_callback,
            ]
        )
        call_kwargs = mock_dbt_runner_class_with_success.return_value.invoke.call_args[
            1
        ]
        assert call_kwargs["log_level"] == "none"
        assert call_kwargs["log_level_file"] == "info"

    def test_runner_force_nodes_as_tasks_with_task_context(
        self,
        mock_runner_with_force_nodes_as_tasks,
        mock_dbt_runner_class_with_success,
        mock_task_context,
    ):
        """Test that runner behavior when _force_nodes_as_tasks is True and in task context."""
        (
            runner,
            mock_logging_callback,
            mock_node_started_callback,
            mock_node_finished_callback,
        ) = mock_runner_with_force_nodes_as_tasks

        result = runner.invoke(["run"])

        assert result.success is True
        assert result.exception is None
        mock_dbt_runner_class_with_success.return_value.invoke.assert_called_once()
        # Verify callbacks are added and log_level is 'none' when in task context
        mock_dbt_runner_class_with_success.assert_called_once_with(
            callbacks=[
                mock_logging_callback,
                mock_node_started_callback,
                mock_node_finished_callback,
            ]
        )
        call_kwargs = mock_dbt_runner_class_with_success.return_value.invoke.call_args[
            1
        ]
        assert call_kwargs["log_level"] == "none"
        assert call_kwargs["log_level_file"] == "info"

    def test_runner_handles_dbt_exceptions(
        self,
        mock_runner_with_callback_mocks,
        mock_dbt_runner_class_with_failure,
        mock_empty_context,
    ):
        """Test that runner handles dbt exceptions gracefully."""
        runner, _, _, _ = mock_runner_with_callback_mocks

        with pytest.raises(ValueError, match="Failed to invoke dbt command"):
            runner.invoke(["run"])

    def test_runner_handles_dbt_failures_with_raise_on_failure_true(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that runner raises on dbt failures when raise_on_failure is True."""
        runner = PrefectDbtRunner(raise_on_failure=True)

        mock_result = Mock()
        mock_result.success = False
        mock_result.exception = None
        mock_result.result = Mock(spec=RunExecutionResult)
        mock_result.result.results = [
            Mock(
                status=RunStatus.Error,
                node=Mock(resource_type="model", name="test_model"),
                message="Test error",
            )
        ]

        mock_dbt_runner_instance = Mock()
        mock_dbt_runner_instance.invoke.return_value = mock_result

        monkeypatch.setattr(
            "prefect_dbt.core.runner.dbtRunner",
            Mock(return_value=mock_dbt_runner_instance),
        )

        # Mock the callback methods
        monkeypatch.setattr(runner, "_create_logging_callback", Mock())
        monkeypatch.setattr(runner, "_create_node_started_callback", Mock())
        monkeypatch.setattr(runner, "_create_node_finished_callback", Mock())

        # Mock context to simulate no flow/task run
        monkeypatch.setattr(
            "prefect_dbt.core.runner.serialize_context", Mock(return_value={})
        )

        # Mock the settings resolve_profiles_yml method to prevent file access
        mock_settings = Mock()
        mock_settings.resolve_profiles_yml.return_value.__enter__ = Mock(
            return_value="/mock/profiles/dir"
        )
        mock_settings.resolve_profiles_yml.return_value.__exit__ = Mock(
            return_value=None
        )
        runner.settings = mock_settings

        with pytest.raises(ValueError, match="Failures detected during invocation"):
            runner.invoke(["run"])

    def test_runner_handles_dbt_failures_with_raise_on_failure_false(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that runner doesn't raise on dbt failures when raise_on_failure is False."""
        runner = PrefectDbtRunner(raise_on_failure=False)

        mock_result = Mock()
        mock_result.success = False
        mock_result.exception = None
        mock_result.result = Mock(spec=RunExecutionResult)
        mock_result.result.results = [
            Mock(
                status=RunStatus.Error,
                node=Mock(resource_type="model", name="test_model"),
                message="Test error",
            )
        ]

        mock_dbt_runner_instance = Mock()
        mock_dbt_runner_instance.invoke.return_value = mock_result

        monkeypatch.setattr(
            "prefect_dbt.core.runner.dbtRunner",
            Mock(return_value=mock_dbt_runner_instance),
        )

        # Mock the callback methods
        monkeypatch.setattr(runner, "_create_logging_callback", Mock())
        monkeypatch.setattr(runner, "_create_node_started_callback", Mock())
        monkeypatch.setattr(runner, "_create_node_finished_callback", Mock())

        # Mock context to simulate no flow/task run
        monkeypatch.setattr(
            "prefect_dbt.core.runner.serialize_context", Mock(return_value={})
        )

        # Mock the settings resolve_profiles_yml method to prevent file access
        mock_settings = Mock()
        mock_settings.resolve_profiles_yml.return_value.__enter__ = Mock(
            return_value="/mock/profiles/dir"
        )
        mock_settings.resolve_profiles_yml.return_value.__exit__ = Mock(
            return_value=None
        )
        runner.settings = mock_settings

        result = runner.invoke(["run"])
        assert result == mock_result

    def test_runner_creates_callbacks_successfully(self):
        """Test that runner creates all required callbacks successfully."""
        runner = PrefectDbtRunner()
        task_state = Mock()
        context = {"test": "context"}
        log_level = EventLevel.INFO

        # Test logging callback creation
        logging_callback = runner._create_logging_callback(
            task_state, log_level, context
        )
        assert callable(logging_callback)

        # Test node started callback creation
        node_started_callback = runner._create_node_started_callback(
            task_state, context
        )
        assert callable(node_started_callback)

        # Test node finished callback creation
        node_finished_callback = runner._create_node_finished_callback(task_state)
        assert callable(node_finished_callback)

    def test_runner_handles_kwargs_and_cli_flags_together(
        self,
        mock_runner_with_callback_mocks,
        mock_dbt_runner_class_with_success,
        mock_empty_context,
    ):
        """Test that runner handles both kwargs and CLI flags together."""
        runner, _, _, _ = mock_runner_with_callback_mocks

        # Test with both kwargs and CLI flags
        result = runner.invoke(
            ["--target-path", "/cli/path", "run"], target_path="/kwargs/path"
        )

        assert result.success is True
        assert result.exception is None
        # CLI flag should take precedence
        assert runner._target_path == Path("/cli/path")

    def test_get_upstream_manifest_nodes_and_configs_returns_correct_structure(
        self, mock_manifest
    ):
        """Test that _get_upstream_manifest_nodes_and_configs returns correct structure."""
        runner = PrefectDbtRunner()

        # Create properly configured mock nodes
        mock_node_1 = Mock(spec=ManifestNode)
        mock_node_1.relation_name = "test_relation_1"
        mock_node_1.config = Mock()
        mock_node_1.config.meta = {"prefect": {"enable_assets": True}}

        mock_node_2 = Mock(spec=ManifestNode)
        mock_node_2.relation_name = "test_relation_2"
        mock_node_2.config = Mock()
        mock_node_2.config.meta = {"prefect": {"enable_assets": False}}

        mock_manifest.nodes = {
            "upstream_node_1": mock_node_1,
            "upstream_node_2": mock_node_2,
        }

        runner._manifest = mock_manifest

        # Create a mock manifest node with dependencies
        mock_node = Mock(spec=ManifestNode)
        mock_node.depends_on_nodes = ["upstream_node_1", "upstream_node_2"]

        result = runner._get_upstream_manifest_nodes_and_configs(mock_node)

        # Verify structure: list of tuples (ManifestNode, dict)
        assert isinstance(result, list)
        assert len(result) == 2

        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], Mock)  # ManifestNode
            assert isinstance(item[1], dict)  # config dict

    def test_get_upstream_manifest_nodes_and_configs_handles_missing_nodes(
        self, mock_manifest
    ):
        """Test that _get_upstream_manifest_nodes_and_configs handles missing nodes gracefully."""
        runner = PrefectDbtRunner()

        # Mock manifest with missing nodes
        mock_manifest.nodes = {}  # Empty nodes dict
        runner._manifest = mock_manifest

        # Create a mock manifest node with dependencies
        mock_node = Mock(spec=ManifestNode)
        mock_node.depends_on_nodes = ["missing_node_1", "missing_node_2"]

        result = runner._get_upstream_manifest_nodes_and_configs(mock_node)

        # Should return empty list when nodes are missing
        assert result == []

    def test_get_upstream_manifest_nodes_and_configs_handles_missing_relation_name(
        self, mock_manifest
    ):
        """Test that _get_upstream_manifest_nodes_and_configs handles missing relation_name."""
        runner = PrefectDbtRunner()

        # Mock manifest and nodes
        mock_node_without_relation = Mock(spec=ManifestNode)
        mock_node_without_relation.relation_name = None  # Missing relation_name
        mock_node_without_relation.config = Mock()
        mock_node_without_relation.config.meta = {}
        mock_manifest.nodes = {"upstream_node": mock_node_without_relation}
        runner._manifest = mock_manifest

        # Create a mock manifest node with dependencies
        mock_node = Mock(spec=ManifestNode)
        mock_node.depends_on_nodes = ["upstream_node"]

        with pytest.raises(ValueError, match="Relation name not found in manifest"):
            runner._get_upstream_manifest_nodes_and_configs(mock_node)

    def test_call_task_with_enable_assets_true_creates_materializing_task(
        self, mock_manifest, mock_manifest_node, monkeypatch
    ):
        """Test that _call_task creates MaterializingTask when enable_assets is True."""
        runner = PrefectDbtRunner()

        runner._manifest = mock_manifest

        # Mock task state
        mock_task_state = Mock()

        # Mock the upstream nodes method to return empty list
        monkeypatch.setattr(
            runner, "_get_upstream_manifest_nodes_and_configs", Mock(return_value=[])
        )

        # Mock task creation methods
        mock_asset = Mock()
        monkeypatch.setattr(
            runner, "_create_asset_from_node", Mock(return_value=mock_asset)
        )
        mock_task_options = {"task_run_name": "test_task", "cache_policy": Mock()}
        monkeypatch.setattr(
            runner, "_create_task_options", Mock(return_value=mock_task_options)
        )

        # Mock MaterializingTask creation
        mock_materializing_task = Mock()
        monkeypatch.setattr(
            "prefect_dbt.core.runner.MaterializingTask",
            Mock(return_value=mock_materializing_task),
        )

        # Mock format_resource_id
        monkeypatch.setattr(
            "prefect_dbt.core.runner.format_resource_id",
            Mock(return_value="test_asset_id"),
        )

        context = {"test": "context"}
        enable_assets = True

        runner._call_task(mock_task_state, mock_manifest_node, context, enable_assets)

        # Verify MaterializingTask was created and started
        mock_task_state.start_task.assert_called_once_with(
            "test_node", mock_materializing_task
        )
        mock_task_state.set_node_dependencies.assert_called_once_with("test_node", [])
        mock_task_state.run_task_in_thread.assert_called_once()

    def test_call_task_with_enable_assets_false_creates_regular_task(
        self, mock_manifest, mock_manifest_node, monkeypatch
    ):
        """Test that _call_task creates regular Task when enable_assets is False."""
        runner = PrefectDbtRunner()

        runner._manifest = mock_manifest

        # Mock task state
        mock_task_state = Mock()

        # Mock the upstream nodes method to return empty list
        monkeypatch.setattr(
            runner, "_get_upstream_manifest_nodes_and_configs", Mock(return_value=[])
        )

        # Mock task creation methods
        mock_task_options = {"task_run_name": "test_task", "cache_policy": Mock()}
        monkeypatch.setattr(
            runner, "_create_task_options", Mock(return_value=mock_task_options)
        )

        # Mock Task creation
        mock_task = Mock()
        monkeypatch.setattr(
            "prefect_dbt.core.runner.Task", Mock(return_value=mock_task)
        )

        context = {"test": "context"}
        enable_assets = False

        runner._call_task(mock_task_state, mock_manifest_node, context, enable_assets)

        # Verify regular Task was created and started
        mock_task_state.start_task.assert_called_once_with("test_node", mock_task)
        mock_task_state.set_node_dependencies.assert_called_once_with("test_node", [])
        mock_task_state.run_task_in_thread.assert_called_once()

    def test_call_task_handles_missing_adapter_type(
        self, mock_manifest, mock_manifest_node
    ):
        """Test that _call_task handles missing adapter type gracefully."""
        runner = PrefectDbtRunner()

        # Mock manifest without adapter type
        mock_manifest.metadata.adapter_type = None
        runner._manifest = mock_manifest

        # Mock task state
        mock_task_state = Mock()

        context = {"test": "context"}
        enable_assets = True

        with pytest.raises(ValueError, match="Adapter type not found in manifest"):
            runner._call_task(
                mock_task_state, mock_manifest_node, context, enable_assets
            )

    def test_call_task_handles_missing_relation_name_for_assets(
        self, mock_manifest, monkeypatch
    ):
        """Test that _call_task handles missing relation_name when creating assets."""
        runner = PrefectDbtRunner()

        runner._manifest = mock_manifest

        # Mock manifest node without relation_name
        mock_node = Mock(spec=ManifestNode)
        mock_node.resource_type = NodeType.Model
        mock_node.unique_id = "test_node"
        mock_node.relation_name = None  # Missing relation_name
        mock_node.config = Mock()
        mock_node.config.meta = {}

        # Mock task state
        mock_task_state = Mock()

        # Mock the upstream nodes method to return empty list
        monkeypatch.setattr(
            runner, "_get_upstream_manifest_nodes_and_configs", Mock(return_value=[])
        )

        context = {"test": "context"}
        enable_assets = True

        with pytest.raises(ValueError, match="Relation name not found in manifest"):
            runner._call_task(mock_task_state, mock_node, context, enable_assets)

    def test_runner_handles_project_loading_successfully(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that runner can load project successfully."""
        mock_project = Mock()

        # Mock Project.from_project_root
        mock_from_project_root = Mock(return_value=mock_project)
        monkeypatch.setattr(
            "prefect_dbt.core.runner.Project.from_project_root",
            mock_from_project_root,
        )

        runner = PrefectDbtRunner()
        runner._project_dir = Path("/test/project")

        # Access project property to trigger loading
        result = runner.project

        assert result == mock_project
        mock_from_project_root.assert_called_once()

    def test_runner_handles_project_loading_with_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that runner uses settings.project_dir when _project_dir is not set."""
        mock_project = Mock()

        # Mock Project.from_project_root
        mock_from_project_root = Mock(return_value=mock_project)
        monkeypatch.setattr(
            "prefect_dbt.core.runner.Project.from_project_root",
            mock_from_project_root,
        )

        # Create settings with project_dir
        settings = PrefectDbtSettings()
        settings.project_dir = Path("/settings/project")

        runner = PrefectDbtRunner(settings=settings)

        # Access project property to trigger loading
        result = runner.project

        assert result == mock_project
        mock_from_project_root.assert_called_once()

    def test_runner_get_compiled_code_path_uses_project_name(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that _get_compiled_code_path uses project.project_name correctly."""
        runner = PrefectDbtRunner()
        runner._project_dir = Path("/test/project")
        runner._target_path = Path("target")

        # Mock project with project_name
        mock_project = Mock()
        mock_project.project_name = "test_project"
        runner._project = mock_project

        # Mock manifest node
        mock_node = Mock(spec=ManifestNode)
        mock_node.original_file_path = "models/test_model.sql"

        result = runner._get_compiled_code_path(mock_node)

        # Should use project.project_name instead of project_dir name
        expected_path = (
            Path("/test/project")
            / "target"
            / "compiled"
            / "test_project"
            / "models/test_model.sql"
        )
        assert result == expected_path

    def test_runner_get_compiled_code_path_triggers_project_loading(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that _get_compiled_code_path triggers project loading when needed."""
        runner = PrefectDbtRunner()
        runner._project_dir = Path("/test/project")
        runner._target_path = Path("target")

        # Mock project with project_name
        mock_project = Mock()
        mock_project.project_name = "test_project"

        # Mock Project.from_project_root
        mock_from_project_root = Mock(return_value=mock_project)
        monkeypatch.setattr(
            "prefect_dbt.core.runner.Project.from_project_root",
            mock_from_project_root,
        )

        # Mock manifest node
        mock_node = Mock(spec=ManifestNode)
        mock_node.original_file_path = "models/test_model.sql"

        result = runner._get_compiled_code_path(mock_node)

        # Should trigger project loading
        mock_from_project_root.assert_called_once()
        expected_path = (
            Path("/test/project")
            / "target"
            / "compiled"
            / "test_project"
            / "models/test_model.sql"
        )
        assert result == expected_path

    def test_runner_get_compiled_code_with_include_compiled_code_true(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that _get_compiled_code works correctly when include_compiled_code is True."""
        runner = PrefectDbtRunner(include_compiled_code=True)
        runner._project_dir = Path("/test/project")
        runner._target_path = Path("target")

        # Mock project with project_name
        mock_project = Mock()
        mock_project.project_name = "test_project"
        runner._project = mock_project

        # Mock manifest node
        mock_node = Mock(spec=ManifestNode)
        mock_node.original_file_path = "models/test_model.sql"

        # Mock file operations
        mock_open = Mock()
        mock_open.return_value.__enter__ = Mock(return_value=Mock())
        mock_open.return_value.__exit__ = Mock(return_value=None)
        monkeypatch.setattr("builtins.open", mock_open)

        # Mock os.path.exists to return True
        monkeypatch.setattr("os.path.exists", Mock(return_value=True))

        # Mock file read
        mock_file_content = Mock()
        mock_file_content.read.return_value = "SELECT * FROM test_table"
        mock_open.return_value.__enter__.return_value = mock_file_content

        result = runner._get_compiled_code(mock_node)

        # Should return compiled code with SQL formatting
        expected_result = "\n ### Compiled code\n```sql\nSELECT * FROM test_table\n```"
        assert result == expected_result

        # Verify the correct path was used
        expected_path = (
            Path("/test/project")
            / "target"
            / "compiled"
            / "test_project"
            / "models/test_model.sql"
        )
        mock_open.assert_called_once_with(expected_path, "r")

    def test_runner_get_compiled_code_with_include_compiled_code_false(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that _get_compiled_code returns empty string when include_compiled_code is False."""
        runner = PrefectDbtRunner(include_compiled_code=False)

        # Mock manifest node
        mock_node = Mock(spec=ManifestNode)

        result = runner._get_compiled_code(mock_node)

        # Should return empty string when include_compiled_code is False
        assert result == ""

    def test_runner_get_compiled_code_with_file_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that _get_compiled_code handles missing compiled code file gracefully."""
        runner = PrefectDbtRunner(include_compiled_code=True)
        runner._project_dir = Path("/test/project")
        runner._target_path = Path("target")

        # Mock project with project_name
        mock_project = Mock()
        mock_project.project_name = "test_project"
        runner._project = mock_project

        # Mock manifest node
        mock_node = Mock(spec=ManifestNode)
        mock_node.original_file_path = "models/test_model.sql"

        # Mock os.path.exists to return False (file doesn't exist)
        monkeypatch.setattr("os.path.exists", Mock(return_value=False))

        result = runner._get_compiled_code(mock_node)

        # Should return empty string when file doesn't exist
        assert result == ""

    def test_runner_invoke_uses_resolve_profiles_yml_context_manager(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that invoke method uses resolve_profiles_yml context manager with actual templated profiles.yml."""
        runner = PrefectDbtRunner()

        mock_result = Mock()
        mock_result.success = True
        mock_result.exception = None

        mock_dbt_runner_instance = Mock()
        mock_dbt_runner_instance.invoke.return_value = mock_result

        mock_dbt_runner_class = Mock(return_value=mock_dbt_runner_instance)
        monkeypatch.setattr(
            "prefect_dbt.core.runner.dbtRunner",
            mock_dbt_runner_class,
        )

        # Mock the callback methods
        monkeypatch.setattr(runner, "_create_logging_callback", Mock())
        monkeypatch.setattr(runner, "_create_node_started_callback", Mock())
        monkeypatch.setattr(runner, "_create_node_finished_callback", Mock())

        # Mock context to simulate no flow/task run
        monkeypatch.setattr(
            "prefect_dbt.core.runner.serialize_context", Mock(return_value={})
        )

        # Create a mock profiles.yml with templated values
        mock_profiles_yml = {
            "my_project": {
                "targets": {
                    "dev": {
                        "type": "snowflake",
                        "account": "{{ prefect.blocks.snowflake-credentials.account }}",
                        "user": "{{ prefect.blocks.snowflake-credentials.user }}",
                        "password": "{{ prefect.blocks.snowflake-credentials.password }}",
                        "database": "{{ prefect.variables.database_name }}",
                        "warehouse": "{{ prefect.variables.warehouse_name }}",
                        "schema": "{{ prefect.variables.schema_name }}",
                    }
                }
            }
        }

        # Mock the load_profiles_yml method to return our templated profiles
        mock_load_method = Mock(return_value=mock_profiles_yml)
        monkeypatch.setattr(
            "prefect_dbt.core.settings.PrefectDbtSettings.load_profiles_yml",
            mock_load_method,
        )

        # Mock the resolve functions to return resolved values
        mock_resolved_profiles = {
            "my_project": {
                "targets": {
                    "dev": {
                        "type": "snowflake",
                        "account": "test-account.snowflakecomputing.com",
                        "user": "test_user",
                        "password": "test_password",
                        "database": "test_database",
                        "warehouse": "test_warehouse",
                        "schema": "test_schema",
                    }
                }
            }
        }

        # Mock the resolve_block_document_references function
        mock_resolve_blocks = Mock(return_value=mock_resolved_profiles)
        monkeypatch.setattr(
            "prefect_dbt.core.settings.resolve_block_document_references",
            mock_resolve_blocks,
        )

        # Mock the resolve_variables function
        mock_resolve_vars = Mock(return_value=mock_resolved_profiles)
        monkeypatch.setattr(
            "prefect_dbt.core.settings.resolve_variables",
            mock_resolve_vars,
        )

        # Mock run_coro_as_sync to return the resolved profiles directly
        def mock_run_coro(coro) -> Any:
            return mock_resolved_profiles

        mock_run_coro_func = Mock(side_effect=mock_run_coro)
        monkeypatch.setattr(
            "prefect_dbt.core.settings.run_coro_as_sync",
            mock_run_coro_func,
        )

        # Mock yaml.dump to verify it's called with resolved profiles
        mock_yaml_dump = Mock()
        monkeypatch.setattr("prefect_dbt.core.settings.yaml.dump", mock_yaml_dump)

        # Mock Path.write_text to verify the resolved profiles are written
        mock_write_text = Mock()
        monkeypatch.setattr("pathlib.Path.write_text", mock_write_text)

        # Call invoke with additional kwargs to test preservation
        result = runner.invoke(["run"], target="dev", threads=4, custom_arg="value")

        assert result == mock_result

        # Verify the profiles were loaded and resolved
        mock_load_method.assert_called_once()
        mock_run_coro_func.assert_called()
        mock_yaml_dump.assert_called_once_with(
            mock_resolved_profiles, default_style=None, default_flow_style=False
        )
        mock_write_text.assert_called_once()

        # Verify dbtRunner was called with the resolved profiles_dir and preserved kwargs
        mock_dbt_runner_instance.invoke.assert_called_once()
        call_kwargs = mock_dbt_runner_instance.invoke.call_args[1]
        assert call_kwargs["target"] == "dev"
        assert call_kwargs["threads"] == 4
        assert call_kwargs["custom_arg"] == "value"

        # Verify the profiles_dir was changed from the original (indicating resolution was used)
        assert call_kwargs["profiles_dir"] != str(runner.profiles_dir)

    def test_runner_loads_graph(self, monkeypatch: pytest.MonkeyPatch):
        """Test that runner loads graph."""
        runner = PrefectDbtRunner()

        # Mock manifest
        mock_manifest = Mock(spec=Manifest)
        runner._manifest = mock_manifest

        # Mock Linker
        mock_linker = Mock()
        monkeypatch.setattr(
            "prefect_dbt.core.runner.Linker", Mock(return_value=mock_linker)
        )

        # Mock Graph
        mock_graph = Mock()
        monkeypatch.setattr(
            "prefect_dbt.core.runner.Graph", Mock(return_value=mock_graph)
        )

        # Access graph property to trigger loading (graph is None initially)
        result = runner.graph

        # Verify graph was created correctly
        assert result == mock_graph
        # Verify Linker was used to link the graph
        mock_linker.link_graph.assert_called_once_with(mock_manifest)

    def test_runner_loads_graph_with_test_edges_for_build_command(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that runner loads graph with test edges when 'build' is in args."""
        runner = PrefectDbtRunner()

        # Mock manifest
        mock_manifest = Mock(spec=Manifest)
        runner._manifest = mock_manifest

        # Mock _set_graph_from_manifest method
        mock_set_graph = Mock()
        monkeypatch.setattr(runner, "_set_graph_from_manifest", mock_set_graph)

        # Mock dbtRunner and successful result
        mock_result = Mock()
        mock_result.success = True
        mock_result.exception = None

        mock_dbt_runner_instance = Mock()
        mock_dbt_runner_instance.invoke.return_value = mock_result

        mock_dbt_runner_class = Mock(return_value=mock_dbt_runner_instance)
        monkeypatch.setattr("prefect_dbt.core.runner.dbtRunner", mock_dbt_runner_class)

        # Mock the callback methods
        monkeypatch.setattr(runner, "_create_logging_callback", Mock())
        monkeypatch.setattr(runner, "_create_node_started_callback", Mock())
        monkeypatch.setattr(runner, "_create_node_finished_callback", Mock())

        # Mock context to simulate flow run (so callbacks are created)
        monkeypatch.setattr(
            "prefect_dbt.core.runner.serialize_context",
            Mock(return_value={"flow_run_context": {"foo": "bar"}}),
        )

        # Mock settings
        mock_settings = Mock()
        mock_settings.resolve_profiles_yml.return_value.__enter__ = Mock(
            return_value="/mock/profiles/dir"
        )
        mock_settings.resolve_profiles_yml.return_value.__exit__ = Mock(
            return_value=None
        )
        runner.settings = mock_settings

        # Call invoke with 'build' command
        runner.invoke(["build"])

        # Verify _create_node_finished_callback was called with add_test_edges=True
        runner._create_node_finished_callback.assert_called_once()
        call_args = runner._create_node_finished_callback.call_args
        assert call_args[1]["add_test_edges"] is True

    def test_runner_loads_graph_with_test_edges_for_retry_build(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that runner loads graph with test edges when retrying 'build' command."""
        runner = PrefectDbtRunner()

        # Mock manifest
        mock_manifest = Mock(spec=Manifest)
        runner._manifest = mock_manifest

        # Mock _set_graph_from_manifest method
        mock_set_graph = Mock()
        monkeypatch.setattr(runner, "_set_graph_from_manifest", mock_set_graph)

        # Mock dbtRunner and successful result
        mock_result = Mock()
        mock_result.success = True
        mock_result.exception = None

        mock_dbt_runner_instance = Mock()
        mock_dbt_runner_instance.invoke.return_value = mock_result

        mock_dbt_runner_class = Mock(return_value=mock_dbt_runner_instance)
        monkeypatch.setattr("prefect_dbt.core.runner.dbtRunner", mock_dbt_runner_class)

        # Mock the callback methods
        monkeypatch.setattr(runner, "_create_logging_callback", Mock())
        monkeypatch.setattr(runner, "_create_node_started_callback", Mock())
        monkeypatch.setattr(runner, "_create_node_finished_callback", Mock())

        # Mock context to simulate flow run (so callbacks are created)
        monkeypatch.setattr(
            "prefect_dbt.core.runner.serialize_context",
            Mock(return_value={"flow_run_context": {"foo": "bar"}}),
        )

        # Mock settings
        mock_settings = Mock()
        mock_settings.resolve_profiles_yml.return_value.__enter__ = Mock(
            return_value="/mock/profiles/dir"
        )
        mock_settings.resolve_profiles_yml.return_value.__exit__ = Mock(
            return_value=None
        )
        runner.settings = mock_settings

        # Mock load_result_state to return previous build results
        mock_previous_results = Mock()
        mock_previous_results.args = {"which": "build"}
        monkeypatch.setattr(
            "prefect_dbt.core.runner.load_result_state",
            Mock(return_value=mock_previous_results),
        )

        # Mock project_dir and target_path
        runner._project_dir = Path("/test/project")
        runner._target_path = Path("target")

        # Call invoke with 'retry' command
        runner.invoke(["retry"])

        # Verify _create_node_finished_callback was called with add_test_edges=True
        runner._create_node_finished_callback.assert_called_once()
        call_args = runner._create_node_finished_callback.call_args
        assert call_args[1]["add_test_edges"] is True

    def test_runner_does_not_load_test_edges_for_non_build_commands(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that runner does not load test edges for non-build commands."""
        runner = PrefectDbtRunner()

        # Mock manifest
        mock_manifest = Mock(spec=Manifest)
        runner._manifest = mock_manifest

        # Mock _set_graph_from_manifest method
        mock_set_graph = Mock()
        monkeypatch.setattr(runner, "_set_graph_from_manifest", mock_set_graph)

        # Mock dbtRunner and successful result
        mock_result = Mock()
        mock_result.success = True
        mock_result.exception = None

        mock_dbt_runner_instance = Mock()
        mock_dbt_runner_instance.invoke.return_value = mock_result

        mock_dbt_runner_class = Mock(return_value=mock_dbt_runner_instance)
        monkeypatch.setattr("prefect_dbt.core.runner.dbtRunner", mock_dbt_runner_class)

        # Mock the callback methods
        monkeypatch.setattr(runner, "_create_logging_callback", Mock())
        monkeypatch.setattr(runner, "_create_node_started_callback", Mock())
        monkeypatch.setattr(runner, "_create_node_finished_callback", Mock())

        # Mock context to simulate flow run (so callbacks are created)
        monkeypatch.setattr(
            "prefect_dbt.core.runner.serialize_context",
            Mock(return_value={"flow_run_context": {"foo": "bar"}}),
        )

        # Mock settings
        mock_settings = Mock()
        mock_settings.resolve_profiles_yml.return_value.__enter__ = Mock(
            return_value="/mock/profiles/dir"
        )
        mock_settings.resolve_profiles_yml.return_value.__exit__ = Mock(
            return_value=None
        )
        runner.settings = mock_settings

        # Call invoke with 'run' command (not build)
        runner.invoke(["run"])

        # Verify _create_node_finished_callback was called with add_test_edges=False
        runner._create_node_finished_callback.assert_called_once()
        call_args = runner._create_node_finished_callback.call_args
        assert call_args[1]["add_test_edges"] is False

    def test_runner_handles_retry_without_previous_results(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that runner handles retry when no previous results exist."""
        runner = PrefectDbtRunner()

        # Mock project_dir and target_path
        runner._project_dir = Path("/test/project")
        runner._target_path = Path("target")

        # Mock load_result_state to return None (no previous results)
        monkeypatch.setattr(
            "prefect_dbt.core.runner.load_result_state", Mock(return_value=None)
        )

        # Call invoke with 'retry' command
        with pytest.raises(ValueError, match="Cannot retry. No previous results found"):
            runner.invoke(["retry"])

    def test_runner_node_finished_callback_rebuilds_graph_with_test_edges(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that the node finished callback rebuilds graph with test edges when needed."""
        runner = PrefectDbtRunner()

        # Mock _set_graph_from_manifest method
        mock_set_graph = Mock()
        monkeypatch.setattr(runner, "_set_graph_from_manifest", mock_set_graph)

        # Mock graph with get_dependent_nodes method
        mock_graph = Mock()
        mock_graph.get_dependent_nodes.return_value = ["dep1", "dep2"]
        runner._graph = mock_graph

        # Create task state
        task_state = Mock()

        # Create callback with add_test_edges=True
        callback = runner._create_node_finished_callback(
            task_state, add_test_edges=True
        )

        # Create mock event for failed node
        mock_event = Mock()
        mock_event.info.name = "NodeFinished"
        mock_event.data.node_info.unique_id = "test_node"

        # Mock MessageToDict to return event data with failed status
        mock_event_data = {"node_info": {"node_status": "error"}}
        monkeypatch.setattr(
            "prefect_dbt.core.runner.MessageToDict", Mock(return_value=mock_event_data)
        )

        # Mock get_dbt_event_msg
        monkeypatch.setattr(
            runner, "get_dbt_event_msg", Mock(return_value="Node failed")
        )

        # Mock _get_manifest_node_and_config to return a node
        mock_node = Mock()
        monkeypatch.setattr(
            runner, "_get_manifest_node_and_config", Mock(return_value=(mock_node, {}))
        )

        # Call the callback
        callback(mock_event)

        # Verify graph was rebuilt with test edges
        mock_set_graph.assert_called_once_with(add_test_edges=True)

        # Verify dependent nodes were added to skipped nodes
        assert "dep1" in runner._skipped_nodes
        assert "dep2" in runner._skipped_nodes

    def test_runner_does_not_create_tasks_for_skipped_nodes(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that runner does not create tasks for nodes that are marked as skipped."""
        runner = PrefectDbtRunner()

        # Add a node to the skipped nodes set
        skipped_node_id = "skipped_node"
        runner._skipped_nodes.add(skipped_node_id)

        # Create task state
        task_state = Mock()

        # Create the node started callback
        callback = runner._create_node_started_callback(task_state, {})

        # Create mock event for the skipped node
        mock_event = Mock()
        mock_event.info.name = "NodeStart"
        mock_event.data.node_info.unique_id = skipped_node_id

        # Mock _get_manifest_node_and_config to return a node (should not be called)
        mock_node = Mock()
        mock_get_config = Mock(return_value=(mock_node, {}))
        monkeypatch.setattr(runner, "_get_manifest_node_and_config", mock_get_config)

        # Mock _call_task (should not be called)
        mock_call_task = Mock()
        monkeypatch.setattr(runner, "_call_task", mock_call_task)

        # Call the callback
        callback(mock_event)

        # Verify that _get_manifest_node_and_config was not called
        mock_get_config.assert_not_called()

        # Verify that _call_task was not called
        mock_call_task.assert_not_called()


class TestExecuteDbtNode:
    """Test cases focusing on execute_dbt_node behavior."""

    def test_execute_dbt_node_completes_successfully(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that execute_dbt_node completes successfully."""
        task_state = Mock()
        node_id = "test_node"
        asset_id = "test_asset"

        # Mock successful completion
        task_state.get_node_status.return_value = {
            "event_data": {"node_info": {"node_status": RunStatus.Success}}
        }

        mock_logger = Mock()
        monkeypatch.setattr(
            "prefect_dbt.core.runner.get_run_logger", Mock(return_value=mock_logger)
        )

        execute_dbt_node(task_state, node_id, asset_id)

        # Verify expected interactions
        task_state.wait_for_node_completion.assert_called_once_with(node_id)
        task_state.get_node_status.assert_called_once_with(node_id)

    def test_execute_dbt_node_handles_failure_status(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that execute_dbt_node handles failure status correctly."""
        task_state = Mock()
        node_id = "test_node"
        asset_id = "test_asset"

        # Mock failure status
        task_state.get_node_status.return_value = {
            "event_data": {"node_info": {"node_status": RunStatus.Error}}
        }

        monkeypatch.setattr("prefect_dbt.core.runner.get_run_logger", Mock())

        with pytest.raises(
            Exception, match="Node test_node finished with status error"
        ):
            execute_dbt_node(task_state, node_id, asset_id)

    def test_execute_dbt_node_handles_no_status(self, monkeypatch: pytest.MonkeyPatch):
        """Test that execute_dbt_node handles missing status gracefully."""
        task_state = Mock()
        node_id = "test_node"
        asset_id = "test_asset"

        # Mock no status returned
        task_state.get_node_status.return_value = None

        monkeypatch.setattr("prefect_dbt.core.runner.get_run_logger", Mock())

        execute_dbt_node(task_state, node_id, asset_id)

        # Verify function completes without error
        task_state.wait_for_node_completion.assert_called_once_with(node_id)
        task_state.get_node_status.assert_called_once_with(node_id)

    def test_execute_dbt_node_with_asset_context(self, monkeypatch: pytest.MonkeyPatch):
        """Test that execute_dbt_node works with asset context."""
        task_state = Mock()
        node_id = "test_node"
        asset_id = "test_asset"

        # Mock successful completion with node info
        node_info = {"node_status": RunStatus.Success, "name": "test_model"}
        task_state.get_node_status.return_value = {
            "event_data": {"node_info": node_info}
        }

        monkeypatch.setattr("prefect_dbt.core.runner.get_run_logger", Mock())

        mock_context = Mock()
        mock_asset_context = Mock()
        mock_asset_context.get.return_value = mock_context
        monkeypatch.setattr("prefect_dbt.core.runner.AssetContext", mock_asset_context)

        execute_dbt_node(task_state, node_id, asset_id)

        # Verify asset metadata was added
        mock_context.add_asset_metadata.assert_called_once_with(asset_id, node_info)
