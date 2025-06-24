"""
Unit tests for PrefectDbtRunner - focusing on outcomes.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest
from dbt.artifacts.schemas.results import RunStatus
from dbt.artifacts.schemas.run import RunExecutionResult
from dbt.contracts.graph.manifest import Manifest
from dbt_common.events.base_types import EventLevel, EventMsg
from prefect_dbt.core.runner import PrefectDbtRunner, execute_dbt_node
from prefect_dbt.core.settings import PrefectDbtSettings


class TestPrefectDbtRunnerOutcomes:
    """Test cases focusing on PrefectDbtRunner outcomes and behavior."""

    def test_runner_initializes_with_working_configuration(self):
        """Test that runner initializes with a working configuration."""
        runner = PrefectDbtRunner()

        # Verify runner has all required components
        assert runner.settings is not None
        assert isinstance(runner.settings, PrefectDbtSettings)
        assert runner.raise_on_failure is True
        assert runner.client is not None

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
        )

        # Verify custom configuration is used
        assert runner.settings == custom_settings
        assert runner.raise_on_failure is False
        assert runner.client == custom_client
        assert runner.include_compiled_code is True

    def test_runner_provides_working_property_accessors(self):
        """Test that runner provides working property accessors."""
        runner = PrefectDbtRunner()

        # Verify all properties return valid values
        assert isinstance(runner.target_path, Path)
        assert isinstance(runner.profiles_dir, Path)
        assert isinstance(runner.project_dir, Path)
        assert isinstance(runner.log_level, EventLevel)

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

    def test_runner_invokes_dbt_successfully(self, monkeypatch: pytest.MonkeyPatch):
        """Test that runner invokes dbt commands successfully."""
        runner = PrefectDbtRunner()

        mock_result = Mock()
        mock_result.success = True
        mock_result.exception = None

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

        result = runner.invoke(["run"])

        assert result == mock_result
        mock_dbt_runner_instance.invoke.assert_called_once()

    def test_runner_handles_dbt_exceptions(self, monkeypatch: pytest.MonkeyPatch):
        """Test that runner handles dbt exceptions gracefully."""
        runner = PrefectDbtRunner()

        mock_result = Mock()
        mock_result.success = False
        mock_result.exception = "Test exception"

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

        with pytest.raises(ValueError, match="Failed to invoke dbt command"):
            runner.invoke(["run"])

    def test_runner_handles_dbt_failures_with_raise_on_failure_true(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that runner handles dbt failures when raise_on_failure is True."""
        runner = PrefectDbtRunner(raise_on_failure=True)

        # Create mock failure result
        mock_node = Mock()
        mock_node.resource_type = "model"
        mock_node.name = "test_model"

        mock_result_item = Mock()
        mock_result_item.node = mock_node
        mock_result_item.status = RunStatus.Error
        mock_result_item.message = "Test error"

        mock_run_result = Mock(spec=RunExecutionResult)
        mock_run_result.results = [mock_result_item]

        mock_result = Mock()
        mock_result.success = False
        mock_result.exception = None
        mock_result.result = mock_run_result

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

        with pytest.raises(ValueError, match="Failures detected"):
            runner.invoke(["run"])

    def test_runner_handles_dbt_failures_with_raise_on_failure_false(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that runner handles dbt failures when raise_on_failure is False."""
        runner = PrefectDbtRunner(raise_on_failure=False)

        mock_result = Mock()
        mock_result.success = False
        mock_result.exception = None

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

        result = runner.invoke(["run"])
        assert result == mock_result

    def test_runner_creates_callbacks_successfully(self):
        """Test that runner creates all required callbacks successfully."""
        runner = PrefectDbtRunner()
        task_state = Mock()
        context = {"test": "context"}

        # Test logging callback
        logging_callback = runner._create_logging_callback(
            task_state, EventLevel.INFO, context
        )
        assert callable(logging_callback)

        # Test node started callback
        started_callback = runner._create_node_started_callback(task_state, context)
        assert callable(started_callback)

        # Test node finished callback
        finished_callback = runner._create_node_finished_callback(task_state)
        assert callable(finished_callback)

    def test_runner_handles_kwargs_and_cli_flags_together(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that runner handles both kwargs and CLI flags together."""
        runner = PrefectDbtRunner()

        # Mock the setting update methods
        mock_kwargs = Mock()
        mock_cli = Mock(return_value=["run"])
        monkeypatch.setattr(runner, "_update_setting_from_kwargs", mock_kwargs)
        monkeypatch.setattr(runner, "_update_setting_from_cli_flag", mock_cli)

        # Mock dbt runner
        mock_dbt_runner_instance = Mock()
        mock_dbt_runner_instance.invoke.return_value = Mock(
            success=True, exception=None
        )
        monkeypatch.setattr(
            "prefect_dbt.core.runner.dbtRunner",
            Mock(return_value=mock_dbt_runner_instance),
        )

        # Mock the callback methods
        monkeypatch.setattr(runner, "_create_logging_callback", Mock())
        monkeypatch.setattr(runner, "_create_node_started_callback", Mock())
        monkeypatch.setattr(runner, "_create_node_finished_callback", Mock())

        runner.invoke(["--target-path", "/cli/path", "run"], target_path="/kwargs/path")

        # Verify both kwargs and CLI flags were processed
        assert mock_kwargs.called
        assert mock_cli.called


class TestExecuteDbtNodeOutcomes:
    """Test cases focusing on execute_dbt_node outcomes and behavior."""

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
        task_state.set_task_logger.assert_called_once_with(node_id, mock_logger)
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
        task_state.set_task_logger.assert_called_once()
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


class TestRunnerConstants:
    """Test cases for runner constants."""

    def test_failure_statuses_include_all_expected_types(self):
        """Test that FAILURE_STATUSES includes all expected failure types."""
        from dbt.artifacts.schemas.results import (
            FreshnessStatus,
            NodeStatus,
            RunStatus,
            TestStatus,
        )
        from prefect_dbt.core.runner import FAILURE_STATUSES

        expected_statuses = [
            RunStatus.Error,
            TestStatus.Error,
            TestStatus.Fail,
            FreshnessStatus.Error,
            FreshnessStatus.RuntimeErr,
            NodeStatus.Error,
            NodeStatus.Fail,
            NodeStatus.RuntimeErr,
        ]

        for status in expected_statuses:
            assert status in FAILURE_STATUSES

    def test_materialization_node_types_include_expected_types(self):
        """Test that MATERIALIZATION_NODE_TYPES includes expected node types."""
        from dbt.artifacts.resources.types import NodeType
        from prefect_dbt.core.runner import MATERIALIZATION_NODE_TYPES

        expected_types = [NodeType.Model, NodeType.Seed, NodeType.Snapshot]

        for node_type in expected_types:
            assert node_type in MATERIALIZATION_NODE_TYPES

    def test_reference_node_types_include_expected_types(self):
        """Test that REFERENCE_NODE_TYPES includes expected node types."""
        from dbt.artifacts.resources.types import NodeType
        from prefect_dbt.core.runner import REFERENCE_NODE_TYPES

        expected_types = [NodeType.Exposure, NodeType.Source]

        for node_type in expected_types:
            assert node_type in REFERENCE_NODE_TYPES
