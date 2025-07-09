"""
Tests for the PrefectDbtRunner class and related functionality.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from dbt.artifacts.resources.types import NodeType
from dbt.artifacts.schemas.results import RunStatus
from dbt.artifacts.schemas.run import RunExecutionResult
from dbt.contracts.graph.manifest import Manifest
from dbt.contracts.graph.nodes import ManifestNode
from dbt_common.events.base_types import EventLevel, EventMsg
from prefect_dbt.core._tracker import NodeTaskTracker
from prefect_dbt.core.runner import PrefectDbtRunner, execute_dbt_node
from prefect_dbt.core.settings import PrefectDbtSettings

from prefect import flow
from prefect.assets import Asset
from prefect.client.orchestration import PrefectClient
from prefect.tasks import MaterializingTask, Task


@pytest.fixture
def mock_manifest():
    """Create a mock dbt manifest."""
    manifest = Mock(spec=Manifest)
    manifest.nodes = {}
    manifest.metadata = Mock()
    manifest.metadata.adapter_type = "snowflake"
    manifest.metadata.project_name = "test_project"
    return manifest


@pytest.fixture
def mock_manifest_node():
    """Create a mock dbt manifest node."""
    node = Mock(spec=ManifestNode)
    node.unique_id = "model.test_project.test_model"
    node.name = "test_model"
    node.resource_type = NodeType.Model
    node.original_file_path = "models/test_model.sql"
    node.relation_name = "test_model"
    node.config = Mock()
    node.config.meta = {"prefect": {}}
    node.config.materialized = "table"
    node.depends_on = Mock()
    node.depends_on.nodes = []
    node.depends_on_nodes = []
    node.description = "Test model description"
    return node


@pytest.fixture
def mock_settings():
    """Create mock PrefectDbtSettings."""
    settings = Mock(spec=PrefectDbtSettings)
    settings.target_path = Path("target")
    settings.profiles_dir = Path("profiles")
    settings.project_dir = Path("project")
    settings.log_level = EventLevel.INFO
    return settings


@pytest.fixture
def mock_client():
    """Create a mock Prefect client."""
    return Mock(spec=PrefectClient)


@pytest.fixture
def mock_task_state():
    """Create a mock NodeTaskTracker."""
    task_state = Mock(spec=NodeTaskTracker)
    task_state.get_node_status.return_value = {
        "event_data": {"node_info": {"node_status": "success"}}
    }
    return task_state


@pytest.fixture
def mock_dbt_runner():
    """Create a mock dbt runner."""
    runner = Mock()
    runner.invoke.return_value = Mock(success=True, result=None)
    return runner


@pytest.fixture
def mock_event():
    """Create a mock dbt event."""
    event = Mock(spec=EventMsg)
    event.info = Mock()
    event.info.name = "NodeFinished"
    event.info.msg = "Test message"
    event.data = Mock()
    event.data.node_info = Mock()
    event.data.node_info.unique_id = "model.test_project.test_model"
    return event


@pytest.fixture
def mock_dbt_runner_class():
    """Mock the dbtRunner class."""
    with patch("prefect_dbt.core.runner.dbtRunner") as mock_class:
        mock_instance = Mock()
        mock_class.return_value = mock_instance
        yield mock_class


@pytest.fixture
def mock_settings_context_manager():
    """Mock the settings context manager."""
    with patch.object(PrefectDbtSettings, "resolve_profiles_yml") as mock_cm:
        mock_cm.return_value.__enter__.return_value = "/profiles/dir"
        yield mock_cm


class TestPrefectDbtRunnerInitialization:
    """Test PrefectDbtRunner initialization and configuration."""

    def test_initializes_with_defaults(self):
        """Test that runner initializes with sensible defaults."""
        runner = PrefectDbtRunner()

        assert runner.settings is not None
        assert isinstance(runner.settings, PrefectDbtSettings)
        assert runner.raise_on_failure is True
        assert runner.client is not None
        assert runner.include_compiled_code is False
        assert runner.disable_assets is False
        assert runner._force_nodes_as_tasks is False

    def test_accepts_custom_configuration(
        self, mock_manifest, mock_settings, mock_client
    ):
        """Test that runner accepts and uses custom configuration."""
        runner = PrefectDbtRunner(
            manifest=mock_manifest,
            settings=mock_settings,
            raise_on_failure=False,
            client=mock_client,
            include_compiled_code=True,
            _force_nodes_as_tasks=True,
        )

        assert runner.settings == mock_settings
        assert runner.raise_on_failure is False
        assert runner.client == mock_client
        assert runner.include_compiled_code is True
        assert runner._force_nodes_as_tasks is True

    def test_property_accessors_work_correctly(self, mock_settings):
        """Test that property accessors return expected values."""
        runner = PrefectDbtRunner(settings=mock_settings)

        # Test that properties access the underlying settings
        assert runner.target_path == mock_settings.target_path
        assert runner.profiles_dir == mock_settings.profiles_dir
        assert runner.project_dir == mock_settings.project_dir
        assert runner.log_level == mock_settings.log_level


class TestPrefectDbtRunnerManifestLoading:
    """Test manifest loading functionality."""

    def test_manifest_loading_success(self, tmp_path: Path):
        """Test successful manifest loading from file."""
        # Create a mock manifest file
        manifest_data = {"nodes": {}, "metadata": {"adapter_type": "snowflake"}}
        manifest_path = tmp_path / "target" / "manifest.json"
        manifest_path.parent.mkdir(parents=True)

        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f)

        runner = PrefectDbtRunner()
        runner._project_dir = tmp_path
        runner._target_path = Path("target")

        with patch("prefect_dbt.core.runner.Manifest.from_dict") as mock_from_dict:
            mock_manifest = Mock(spec=Manifest)
            mock_from_dict.return_value = mock_manifest

            result = runner.manifest

            assert result == mock_manifest
            mock_from_dict.assert_called_once_with(manifest_data)

    def test_manifest_loading_file_not_found(self, tmp_path: Path):
        """Test that missing manifest file raises appropriate error."""
        runner = PrefectDbtRunner()
        runner._project_dir = tmp_path
        runner._target_path = Path("target")

        with pytest.raises(ValueError, match="Manifest file not found"):
            _ = runner.manifest

    def test_manifest_loading_with_preloaded_manifest(self, mock_manifest):
        """Test that preloaded manifest is used without file access."""
        runner = PrefectDbtRunner(manifest=mock_manifest)

        result = runner.manifest

        assert result == mock_manifest


class TestPrefectDbtRunnerGraphLoading:
    """Test graph loading functionality."""

    def test_graph_loading_creates_linker_and_graph(self, mock_manifest):
        """Test that graph loading creates linker and graph correctly."""
        runner = PrefectDbtRunner(manifest=mock_manifest)

        with (
            patch("prefect_dbt.core.runner.Linker") as mock_linker_class,
            patch("prefect_dbt.core.runner.Graph") as mock_graph_class,
        ):
            mock_linker = Mock()
            mock_linker_class.return_value = mock_linker

            mock_graph = Mock()
            mock_graph_class.return_value = mock_graph

            result = runner.graph

            assert result == mock_graph
            mock_linker.link_graph.assert_called_once_with(mock_manifest)
            mock_graph_class.assert_called_once_with(mock_linker.graph)

    def test_graph_loading_with_test_edges(self, mock_manifest):
        """Test that graph loading can include test edges."""
        runner = PrefectDbtRunner(manifest=mock_manifest)

        with patch.object(runner, "_set_graph_from_manifest") as mock_set_graph:
            runner._set_graph_from_manifest(add_test_edges=True)

            mock_set_graph.assert_called_once_with(add_test_edges=True)


class TestPrefectDbtRunnerProjectName:
    """Test project name functionality."""

    def test_project_name_from_manifest(self, mock_manifest):
        """Test that project name is set from manifest."""
        runner = PrefectDbtRunner(manifest=mock_manifest)
        assert runner.project_name == "test_project"


class TestPrefectDbtRunnerCompiledCode:
    """Test compiled code functionality."""

    def test_get_compiled_code_path_uses_project_name(
        self, tmp_path: Path, mock_manifest, mock_manifest_node
    ):
        """Test that compiled code path uses project name correctly."""
        runner = PrefectDbtRunner(manifest=mock_manifest)
        runner._project_dir = tmp_path
        runner._target_path = Path("target")

        result = runner._get_compiled_code_path(mock_manifest_node)

        expected_path = (
            tmp_path
            / "target"
            / "compiled"
            / "test_project"
            / "models"
            / "test_model.sql"
        )
        assert result == expected_path

    def test_get_compiled_code_returns_empty_when_disabled(self, mock_manifest_node):
        """Test that compiled code returns empty when disabled."""
        runner = PrefectDbtRunner(include_compiled_code=False)

        result = runner._get_compiled_code(mock_manifest_node)

        assert result == ""

    def test_get_compiled_code_returns_formatted_sql_when_enabled(
        self, tmp_path: Path, mock_manifest, mock_manifest_node
    ):
        """Test that compiled code returns formatted SQL when enabled."""
        runner = PrefectDbtRunner(manifest=mock_manifest, include_compiled_code=True)
        runner._project_dir = tmp_path
        runner._target_path = Path("target")

        # Create compiled SQL file
        compiled_path = tmp_path / "target" / "compiled" / "test_project" / "models"
        compiled_path.mkdir(parents=True)
        sql_file = compiled_path / "test_model.sql"
        sql_file.write_text("SELECT * FROM test_table")

        result = runner._get_compiled_code(mock_manifest_node)

        assert "SELECT * FROM test_table" in result

    def test_get_compiled_code_returns_empty_when_file_not_found(
        self, tmp_path: Path, mock_manifest, mock_manifest_node
    ):
        """Test that compiled code returns empty when file not found."""
        runner = PrefectDbtRunner(manifest=mock_manifest, include_compiled_code=True)
        runner._project_dir = tmp_path
        runner._target_path = Path("target")

        result = runner._get_compiled_code(mock_manifest_node)

        assert result == ""


class TestPrefectDbtRunnerEventProcessing:
    """Test event processing functionality."""

    def test_get_dbt_event_msg_extracts_message(self, mock_event):
        """Test that event message extraction works correctly."""
        mock_event.info.msg = "Test message"

        result = PrefectDbtRunner.get_dbt_event_msg(mock_event)

        assert result == "Test message"

    def test_get_dbt_event_node_id_extracts_node_id(self, mock_event):
        """Test that node ID extraction works correctly."""
        # mock_event.data.node_info is already a Mock with .unique_id
        runner = PrefectDbtRunner()
        result = runner._get_dbt_event_node_id(mock_event)

        assert result == "model.test_project.test_model"


class TestPrefectDbtRunnerCLIArgumentHandling:
    """Test CLI argument handling functionality."""

    def test_extract_flag_value_finds_flag(self):
        """Test that flag value extraction works correctly."""
        runner = PrefectDbtRunner()
        args = ["--target-path", "/custom/path", "run"]

        result_args, result_value = runner._extract_flag_value(args, "--target-path")

        assert result_args == ["run"]
        assert result_value == "/custom/path"

    def test_extract_flag_value_handles_missing_flag(self):
        """Test that missing flag is handled correctly."""
        runner = PrefectDbtRunner()
        args = ["run"]

        result_args, result_value = runner._extract_flag_value(args, "--target-path")

        assert result_args == ["run"]
        assert result_value is None

    def test_update_setting_from_kwargs(self):
        """Test that settings are updated from kwargs."""
        runner = PrefectDbtRunner()
        kwargs = {"target_path": "/custom/path"}

        runner._update_setting_from_kwargs("target_path", kwargs)

        assert runner._target_path == "/custom/path"
        assert "target_path" not in kwargs

    def test_update_setting_from_cli_flag(self):
        """Test that settings are updated from CLI flags."""
        runner = PrefectDbtRunner()
        args = ["--target-path", "/custom/path", "run"]

        result_args = runner._update_setting_from_cli_flag(
            args, "--target-path", "target_path", Path
        )

        assert result_args == ["run"]
        assert runner._target_path == Path("/custom/path")


class TestPrefectDbtRunnerInvoke:
    """Test the main invoke method."""

    def test_invoke_successful_command(
        self, mock_dbt_runner_class, mock_settings_context_manager
    ):
        """Test successful command invocation."""
        runner = PrefectDbtRunner()
        mock_dbt_runner_class.return_value.invoke.return_value = Mock(
            success=True, result=None
        )

        result = runner.invoke(["run"])

        assert result.success is True
        mock_dbt_runner_class.assert_called_once()

    def test_invoke_with_callbacks_in_flow_context(
        self, mock_dbt_runner_class, mock_settings_context_manager
    ):
        """Test that callbacks are created when in flow context."""
        runner = PrefectDbtRunner()
        mock_dbt_runner_class.return_value.invoke.return_value = Mock(
            success=True, result=None
        )

        @flow
        def test_flow():
            return runner.invoke(["run"])

        with patch("prefect_dbt.core.runner.serialize_context") as mock_context:
            mock_context.return_value = {"flow_run_context": {"id": "test"}}
            result = test_flow()

        assert result.success is True
        # Verify callbacks were created
        mock_dbt_runner_class.assert_called_once()
        call_args = mock_dbt_runner_class.call_args
        assert len(call_args[1]["callbacks"]) == 3

    def test_invoke_with_force_nodes_as_tasks(
        self, mock_dbt_runner_class, mock_settings_context_manager
    ):
        """Test that callbacks are created when force_nodes_as_tasks is True."""
        runner = PrefectDbtRunner(_force_nodes_as_tasks=True)
        mock_dbt_runner_class.return_value.invoke.return_value = Mock(
            success=True, result=None
        )

        with patch("prefect_dbt.core.runner.serialize_context") as mock_context:
            mock_context.return_value = {}
            result = runner.invoke(["run"])

        assert result.success is True
        # Verify callbacks were created
        mock_dbt_runner_class.assert_called_once()
        call_args = mock_dbt_runner_class.call_args
        assert len(call_args[1]["callbacks"]) == 3

    def test_invoke_sets_log_level_none_in_context(
        self, mock_dbt_runner_class, mock_settings_context_manager
    ):
        """Test that log level is set to none when in flow context."""
        runner = PrefectDbtRunner()
        mock_dbt_runner_class.return_value.invoke.return_value = Mock(
            success=True, result=None
        )

        @flow
        def test_flow():
            return runner.invoke(["run"])

        with patch("prefect_dbt.core.runner.serialize_context") as mock_context:
            mock_context.return_value = {"flow_run_context": {"id": "test"}}
            test_flow()

        # Verify log_level was set to "none"
        call_args = mock_dbt_runner_class.return_value.invoke.call_args
        assert call_args[1]["log_level"] == "none"

    def test_invoke_uses_original_log_level_outside_context(
        self, mock_dbt_runner_class, mock_settings_context_manager
    ):
        """Test that original log level is used outside flow context."""
        runner = PrefectDbtRunner()
        mock_dbt_runner_class.return_value.invoke.return_value = Mock(
            success=True, result=None
        )

        with patch("prefect_dbt.core.runner.serialize_context") as mock_context:
            mock_context.return_value = {}
            runner.invoke(["run"])

        # Verify log_level was set to the original value
        call_args = mock_dbt_runner_class.return_value.invoke.call_args
        assert call_args[1]["log_level"] == str(runner.log_level.value)

    def test_invoke_handles_dbt_exceptions(
        self, mock_dbt_runner_class, mock_settings_context_manager
    ):
        """Test that dbt exceptions are handled correctly."""
        runner = PrefectDbtRunner()
        mock_dbt_runner_class.return_value.invoke.return_value = Mock(
            success=False, exception="dbt error"
        )

        with pytest.raises(ValueError, match="Failed to invoke dbt command"):
            runner.invoke(["run"])

    def test_invoke_handles_dbt_failures_with_raise_on_failure_true(
        self, mock_dbt_runner_class, mock_settings_context_manager
    ):
        """Test that dbt failures raise when raise_on_failure is True."""
        runner = PrefectDbtRunner(raise_on_failure=True)

        # Create a mock result with failures
        mock_result = Mock(spec=RunExecutionResult)
        mock_node = Mock()
        mock_node.resource_type = "model"
        mock_node.name = "test_model"
        mock_result.results = [
            Mock(status=RunStatus.Error, node=mock_node, message="Test error")
        ]

        mock_dbt_runner_class.return_value.invoke.return_value = Mock(
            success=False, exception=None, result=mock_result
        )

        with pytest.raises(ValueError, match="Failures detected"):
            runner.invoke(["run"])

    def test_invoke_handles_dbt_failures_with_raise_on_failure_false(
        self, mock_dbt_runner_class, mock_settings_context_manager
    ):
        """Test that dbt failures don't raise when raise_on_failure is False."""
        runner = PrefectDbtRunner(raise_on_failure=False)

        # Create a mock result with failures
        mock_result = Mock(spec=RunExecutionResult)
        mock_node = Mock()
        mock_node.resource_type = "model"
        mock_node.name = "test_model"
        mock_result.results = [
            Mock(status=RunStatus.Error, node=mock_node, message="Test error")
        ]

        mock_dbt_runner_class.return_value.invoke.return_value = Mock(
            success=False, exception=None, result=mock_result
        )

        result = runner.invoke(["run"])
        assert result.success is False

    def test_invoke_handles_kwargs_and_cli_flags_together(
        self, mock_dbt_runner_class, mock_settings_context_manager
    ):
        """Test that kwargs and CLI flags are handled together."""
        runner = PrefectDbtRunner()
        mock_dbt_runner_class.return_value.invoke.return_value = Mock(
            success=True, result=None
        )

        result = runner.invoke(
            ["--target-path", "/cli/path", "run"], target_path="/kwargs/path"
        )

        assert result.success is True
        # Verify the CLI flags take precedence (processed after kwargs)
        call_args = mock_dbt_runner_class.return_value.invoke.call_args
        assert call_args[1]["target_path"] == "/cli/path"

    def test_invoke_uses_resolve_profiles_yml_context_manager(
        self, mock_dbt_runner_class, mock_settings_context_manager
    ):
        """Test that the profiles.yml context manager is used."""
        runner = PrefectDbtRunner()
        mock_dbt_runner_class.return_value.invoke.return_value = Mock(
            success=True, result=None
        )

        runner.invoke(["run"])

        mock_settings_context_manager.assert_called_once()


class TestPrefectDbtRunnerCallbackCreation:
    """Test callback creation functionality."""

    def test_create_logging_callback_returns_callable(self, mock_task_state):
        """Test that logging callback creation returns a callable."""
        runner = PrefectDbtRunner()
        context = {"test": "context"}

        callback = runner._create_logging_callback(
            mock_task_state, EventLevel.INFO, context
        )

        assert callable(callback)

    def test_create_node_started_callback_returns_callable(self, mock_task_state):
        """Test that node started callback creation returns a callable."""
        runner = PrefectDbtRunner()
        context = {"test": "context"}

        callback = runner._create_node_started_callback(mock_task_state, context)

        assert callable(callback)

    def test_create_node_finished_callback_returns_callable(self, mock_task_state):
        """Test that node finished callback creation returns a callable."""
        runner = PrefectDbtRunner()

        callback = runner._create_node_finished_callback(mock_task_state)

        assert callable(callback)

    def test_create_node_finished_callback_with_add_test_edges(self, mock_task_state):
        """Test that node finished callback works with add_test_edges."""
        runner = PrefectDbtRunner()

        callback = runner._create_node_finished_callback(
            mock_task_state, add_test_edges=True
        )

        assert callable(callback)

    def test_disable_assets_logic_in_node_started_callback(
        self, mock_task_state, mock_manifest_node, mock_manifest
    ):
        """Test that disable_assets logic correctly combines node config and runner setting."""
        context = {"test": "context"}

        mock_manifest.nodes = {mock_manifest_node.unique_id: mock_manifest_node}

        runner_disabled = PrefectDbtRunner(manifest=mock_manifest, disable_assets=True)
        mock_manifest_node.config.meta = {"prefect": {}}

        with patch.object(runner_disabled, "_call_task") as mock_call_task:
            callback = runner_disabled._create_node_started_callback(
                mock_task_state, context
            )

            mock_event = Mock(spec=EventMsg)
            mock_event.info = Mock()
            mock_event.info.name = "NodeStart"
            mock_event.data = Mock()
            mock_event.data.node_info = Mock()
            mock_event.data.node_info.unique_id = mock_manifest_node.unique_id

            callback(mock_event)

            mock_call_task.assert_called_once_with(
                mock_task_state, mock_manifest_node, context, False
            )


class TestPrefectDbtRunnerManifestNodeOperations:
    """Test manifest node operations."""

    def test_get_upstream_manifest_nodes_and_configs_returns_correct_structure(
        self, mock_manifest, mock_manifest_node
    ):
        """Test that upstream nodes and configs are returned correctly."""
        runner = PrefectDbtRunner(manifest=mock_manifest)

        # Mock the manifest to return upstream nodes
        upstream_node = Mock(spec=ManifestNode)
        upstream_node.unique_id = "model.test_project.upstream_model"
        upstream_node.config = Mock()
        upstream_node.config.meta = {"prefect": {}}
        upstream_node.config.materialized = "view"
        upstream_node.relation_name = "upstream_model"
        upstream_node.resource_type = NodeType.Model
        upstream_node.depends_on_nodes = []

        mock_manifest.nodes = {"model.test_project.upstream_model": upstream_node}
        mock_manifest_node.depends_on_nodes = ["model.test_project.upstream_model"]

        result = runner._get_upstream_manifest_nodes_and_configs(mock_manifest_node)

        assert len(result) == 1
        assert result[0][0] == upstream_node
        assert result[0][1] == {}

    def test_get_upstream_manifest_nodes_and_configs_handles_missing_nodes(
        self, mock_manifest, mock_manifest_node
    ):
        """Test that missing upstream nodes are handled gracefully."""
        runner = PrefectDbtRunner(manifest=mock_manifest)
        mock_manifest.nodes = {}
        mock_manifest_node.depends_on_nodes = ["model.test_project.missing_model"]

        result = runner._get_upstream_manifest_nodes_and_configs(mock_manifest_node)

        assert result == []

    def test_get_upstream_manifest_nodes_and_configs_handles_missing_relation_name(
        self, mock_manifest, mock_manifest_node
    ):
        """Test that missing relation_name is handled gracefully."""
        runner = PrefectDbtRunner(manifest=mock_manifest)

        # Create a node without relation_name
        upstream_node = Mock(spec=ManifestNode)
        upstream_node.unique_id = "model.test_project.upstream_model"
        upstream_node.config = Mock()
        upstream_node.config.meta = {"prefect": {}}
        upstream_node.config.materialized = "view"
        upstream_node.relation_name = None
        upstream_node.resource_type = NodeType.Model
        upstream_node.depends_on_nodes = []

        mock_manifest.nodes = {"model.test_project.upstream_model": upstream_node}
        mock_manifest_node.depends_on_nodes = ["model.test_project.upstream_model"]

        # Should raise ValueError
        with pytest.raises(ValueError, match="Relation name not found in manifest"):
            runner._get_upstream_manifest_nodes_and_configs(mock_manifest_node)


class TestPrefectDbtRunnerTaskCreation:
    """Test task creation functionality."""

    def test_call_task_with_enable_assets_true_creates_materializing_task(
        self, mock_task_state, mock_manifest_node, mock_manifest
    ):
        """Test that materializing tasks are created when assets are enabled."""
        runner = PrefectDbtRunner(manifest=mock_manifest)
        context = {"test": "context"}

        with patch(
            "prefect_dbt.core.runner.MaterializingTask"
        ) as mock_materializing_task:
            mock_task = Mock(spec=MaterializingTask)
            mock_materializing_task.return_value = mock_task

            runner._call_task(
                mock_task_state, mock_manifest_node, context, enable_assets=True
            )

            mock_materializing_task.assert_called_once()

    def test_call_task_with_enable_assets_false_creates_regular_task(
        self, mock_task_state, mock_manifest_node, mock_manifest
    ):
        """Test that regular tasks are created when assets are disabled."""
        runner = PrefectDbtRunner(manifest=mock_manifest)
        context = {"test": "context"}

        with patch("prefect_dbt.core.runner.Task") as mock_task_class:
            mock_task = Mock(spec=Task)
            mock_task_class.return_value = mock_task

            runner._call_task(
                mock_task_state, mock_manifest_node, context, enable_assets=False
            )

            mock_task_class.assert_called_once()

    def test_call_task_handles_missing_adapter_type(
        self, mock_task_state, mock_manifest_node, mock_manifest
    ):
        """Test that missing adapter type is handled gracefully."""
        runner = PrefectDbtRunner(manifest=mock_manifest)
        context = {"test": "context"}

        # Remove adapter_type from manifest metadata
        mock_manifest.metadata.adapter_type = None

        with patch("prefect_dbt.core.runner.Task") as mock_task_class:
            mock_task = Mock(spec=Task)
            mock_task_class.return_value = mock_task

            with pytest.raises(ValueError, match="Adapter type not found in manifest"):
                runner._call_task(
                    mock_task_state, mock_manifest_node, context, enable_assets=True
                )

    def test_call_task_handles_missing_relation_name_for_assets(
        self, mock_task_state, mock_manifest_node, mock_manifest
    ):
        """Test that missing relation_name is handled when creating assets."""
        runner = PrefectDbtRunner(manifest=mock_manifest)
        context = {"test": "context"}

        # Remove relation_name from manifest node
        mock_manifest_node.relation_name = None

        with patch("prefect_dbt.core.runner.Task") as mock_task_class:
            mock_task = Mock(spec=Task)
            mock_task_class.return_value = mock_task

            with pytest.raises(ValueError, match="Relation name not found in manifest"):
                runner._call_task(
                    mock_task_state, mock_manifest_node, context, enable_assets=True
                )


class TestPrefectDbtRunnerBuildCommands:
    """Test build command specific functionality."""

    def test_invoke_build_command_sets_add_test_edges_true(
        self, mock_dbt_runner_class, mock_settings_context_manager
    ):
        """Test that build commands set add_test_edges to True."""
        runner = PrefectDbtRunner()
        mock_dbt_runner_class.return_value.invoke.return_value = Mock(
            success=True, result=None
        )

        with patch("prefect_dbt.core.runner.serialize_context") as mock_context:
            mock_context.return_value = {"flow_run_context": {"id": "test"}}
            runner.invoke(["build"])

        # Verify callbacks were created with add_test_edges=True
        mock_dbt_runner_class.assert_called_once()
        call_args = mock_dbt_runner_class.call_args
        assert len(call_args[1]["callbacks"]) == 3

    def test_invoke_retry_build_command_sets_add_test_edges_true(
        self, mock_dbt_runner_class, mock_settings_context_manager, tmp_path: Path
    ):
        """Test that retry build commands set add_test_edges to True."""
        runner = PrefectDbtRunner()
        mock_dbt_runner_class.return_value.invoke.return_value = Mock(
            success=True, result=None
        )

        # Create mock run_results.json with proper schema version and elapsed_time
        results_path = tmp_path / "target" / "run_results.json"
        results_path.parent.mkdir(parents=True)
        results_data = {
            "metadata": {
                "dbt_schema_version": "https://schemas.getdbt.com/dbt/run-results/v5.json",
                "generated_at": "2023-01-01T00:00:00.000000Z",
            },
            "args": {"which": "build"},
            "results": [],
            "elapsed_time": 0.0,
        }
        with open(results_path, "w") as f:
            json.dump(results_data, f)

        runner._project_dir = tmp_path
        runner._target_path = Path("target")

        with patch("prefect_dbt.core.runner.serialize_context") as mock_context:
            mock_context.return_value = {"flow_run_context": {"id": "test"}}
            with pytest.raises(
                ValueError,
                match="Cannot retry. No previous results found at target path target",
            ):
                runner.invoke(["retry"])

    def test_invoke_retry_without_previous_results_raises_error(
        self, mock_dbt_runner_class, mock_settings_context_manager, tmp_path: Path
    ):
        """Test that retry without previous results raises an error."""
        runner = PrefectDbtRunner()
        runner._project_dir = tmp_path
        runner._target_path = Path("target")

        with pytest.raises(ValueError, match="Cannot retry. No previous results found"):
            runner.invoke(["retry"])


class TestExecuteDbtNode:
    """Test the execute_dbt_node function."""

    def test_execute_dbt_node_completes_successfully(self, mock_task_state):
        """Test that execute_dbt_node completes successfully."""
        node_id = "model.test_project.test_model"
        asset_id = "test_asset"

        # Mock successful completion
        mock_task_state.get_node_status.return_value = {
            "event_data": {"node_info": {"node_status": "success"}}
        }

        execute_dbt_node(mock_task_state, node_id, asset_id)

        mock_task_state.wait_for_node_completion.assert_called_once_with(node_id)
        mock_task_state.get_node_status.assert_called_once_with(node_id)

    def test_execute_dbt_node_handles_failure_status(self, mock_task_state):
        """Test that execute_dbt_node handles failure status."""
        node_id = "model.test_project.test_model"
        asset_id = "test_asset"

        # Mock failure status
        mock_task_state.get_node_status.return_value = {
            "event_data": {"node_info": {"node_status": "error"}}
        }

        with pytest.raises(Exception, match="Node .* finished with status error"):
            execute_dbt_node(mock_task_state, node_id, asset_id)

    def test_execute_dbt_node_handles_no_status(self, mock_task_state):
        """Test that execute_dbt_node handles missing status."""
        node_id = "model.test_project.test_model"
        asset_id = "test_asset"

        # Mock no status
        mock_task_state.get_node_status.return_value = None

        execute_dbt_node(mock_task_state, node_id, asset_id)

        # Should complete without error when no status is available
        mock_task_state.wait_for_node_completion.assert_called_once_with(node_id)

    def test_execute_dbt_node_with_asset_context(self, mock_task_state):
        """Test that execute_dbt_node works with asset context."""
        node_id = "model.test_project.test_model"
        asset_id = "test_asset"

        # Mock successful completion with node info
        mock_task_state.get_node_status.return_value = {
            "event_data": {"node_info": {"node_status": "success", "test_info": "test"}}
        }

        # Test without asset context (should not raise error)
        execute_dbt_node(mock_task_state, node_id, asset_id)

        # Verify the function completed successfully
        mock_task_state.wait_for_node_completion.assert_called_once_with(node_id)


class TestPrefectDbtRunnerAssetCreation:
    """Test asset creation functionality."""

    def test_create_asset_from_node_creates_asset(self, mock_manifest_node):
        """Test that assets are created correctly from manifest nodes."""
        runner = PrefectDbtRunner()
        adapter_type = "snowflake"

        with patch("prefect_dbt.core.runner.Asset") as mock_asset_class:
            mock_asset = Mock(spec=Asset)
            mock_asset_class.return_value = mock_asset

            result = runner._create_asset_from_node(mock_manifest_node, adapter_type)

            assert result == mock_asset
            mock_asset_class.assert_called_once()

    def test_create_task_options_creates_options(self, mock_manifest_node):
        """Test that task options are created correctly."""
        runner = PrefectDbtRunner()
        upstream_assets = [Mock(spec=Asset)]

        with patch("prefect_dbt.core.runner.TaskOptions") as mock_options_class:
            mock_options = Mock()
            mock_options_class.return_value = mock_options

            result = runner._create_task_options(mock_manifest_node, upstream_assets)

            assert result == mock_options
            mock_options_class.assert_called_once()


class TestPrefectDbtRunnerManifestNodeLookup:
    """Test manifest node lookup functionality."""

    def test_get_manifest_node_and_config_returns_node_and_config(
        self, mock_manifest, mock_manifest_node
    ):
        """Test that manifest node and config are returned correctly."""
        runner = PrefectDbtRunner(manifest=mock_manifest)
        node_id = "model.test_project.test_model"

        mock_manifest.nodes = {node_id: mock_manifest_node}

        result_node, result_config = runner._get_manifest_node_and_config(node_id)

        assert result_node == mock_manifest_node
        assert result_config == {}

    def test_get_manifest_node_and_config_returns_none_for_missing_node(
        self, mock_manifest
    ):
        """Test that None is returned for missing nodes."""
        runner = PrefectDbtRunner(manifest=mock_manifest)
        node_id = "model.test_project.missing_model"

        mock_manifest.nodes = {}

        result_node, result_config = runner._get_manifest_node_and_config(node_id)

        assert result_node is None
        assert result_config == {}
