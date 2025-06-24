"""
Unit tests for prefect-dbt runner
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from dbt.artifacts.schemas.results import (
    FreshnessStatus,
    NodeStatus,
    RunStatus,
    TestStatus,
)
from dbt.artifacts.schemas.run import RunExecutionResult
from dbt.contracts.graph.manifest import Manifest
from dbt.contracts.graph.nodes import ManifestNode
from dbt_common.events.base_types import EventLevel, EventMsg
from prefect_dbt.core.runner import (
    FAILURE_STATUSES,
    MATERIALIZATION_NODE_TYPES,
    REFERENCE_NODE_TYPES,
    PrefectDbtRunner,
    execute_dbt_node,
)
from prefect_dbt.core.settings import PrefectDbtSettings
from prefect_dbt.core.task_state import TaskState


class TestPrefectDbtRunner:
    """Test cases for PrefectDbtRunner class"""

    def test_default_initialization(self) -> None:
        """Test default initialization"""
        runner = PrefectDbtRunner()

        assert runner.settings is not None
        assert isinstance(runner.settings, PrefectDbtSettings)
        assert runner.raise_on_failure is True
        assert runner.include_compiled_code is False
        assert runner._manifest is None

    def test_custom_initialization(self) -> None:
        """Test initialization with custom parameters"""
        settings = PrefectDbtSettings()
        manifest = Mock(spec=Manifest)
        client = Mock()

        runner = PrefectDbtRunner(
            manifest=manifest,
            settings=settings,
            raise_on_failure=False,
            client=client,
            include_compiled_code=True,
        )

        assert runner._manifest == manifest
        assert runner.settings == settings
        assert runner.raise_on_failure is False
        assert runner.client == client
        assert runner.include_compiled_code is True

    def test_property_accessors(self) -> None:
        """Test property accessors for settings"""
        runner = PrefectDbtRunner()

        # Test default values from settings
        assert runner.target_path == runner.settings.target_path
        assert runner.profiles_dir == runner.settings.profiles_dir
        assert runner.project_dir == runner.settings.project_dir
        assert runner.log_level == runner.settings.log_level

    def test_property_accessors_with_overrides(self) -> None:
        """Test property accessors with overridden values"""
        runner = PrefectDbtRunner()

        # Override values
        runner._target_path = Path("/custom/target")
        runner._profiles_dir = Path("/custom/profiles")
        runner._project_dir = Path("/custom/project")
        runner._log_level = EventLevel.DEBUG

        assert runner.target_path == Path("/custom/target")
        assert runner.profiles_dir == Path("/custom/profiles")
        assert runner.project_dir == Path("/custom/project")
        assert runner.log_level == EventLevel.DEBUG

    @patch("builtins.open")
    @patch("json.load")
    def test_manifest_property_loads_from_file(
        self, mock_json_load: Mock, mock_open: Mock
    ) -> None:
        """Test manifest property loads from file when not provided"""
        mock_manifest = Mock(spec=Manifest)
        mock_json_load.return_value = {"test": "data"}

        with patch.object(Manifest, "from_dict", return_value=mock_manifest):
            runner = PrefectDbtRunner()
            runner._target_path = Path("target")
            runner._project_dir = Path("/test/project")

            result = runner.manifest

            assert result == mock_manifest
            mock_open.assert_called_once_with("/test/project/target/manifest.json", "r")

    @patch("builtins.open")
    def test_manifest_property_file_not_found(self, mock_open: Mock) -> None:
        """Test manifest property raises error when file not found"""
        mock_open.side_effect = FileNotFoundError()

        runner = PrefectDbtRunner()
        runner._target_path = Path("target")
        runner._project_dir = Path("/test/project")

        with pytest.raises(ValueError, match="Manifest file not found"):
            _ = runner.manifest

    def test_get_node_prefect_config(self) -> None:
        """Test getting prefect config from manifest node"""
        runner = PrefectDbtRunner()

        manifest_node = Mock(spec=ManifestNode)
        manifest_node.config = Mock()
        manifest_node.config.meta = {"prefect": {"test": "config"}}

        result = runner._get_node_prefect_config(manifest_node)
        assert result == {"test": "config"}

    def test_get_upstream_manifest_nodes(self) -> None:
        """Test getting upstream manifest nodes"""
        runner = PrefectDbtRunner()

        # Create mock manifest with nodes
        manifest = Mock(spec=Manifest)
        upstream_node = Mock(spec=ManifestNode)
        upstream_node.relation_name = "upstream_table"

        manifest_node = Mock(spec=ManifestNode)
        manifest_node.depends_on_nodes = ["upstream_node_id"]

        manifest.nodes = {"upstream_node_id": upstream_node}
        runner._manifest = manifest

        result = runner._get_upstream_manifest_nodes(manifest_node)
        assert result == [upstream_node]

    def test_get_upstream_manifest_nodes_missing_relation_name(self) -> None:
        """Test getting upstream nodes when relation name is missing"""
        runner = PrefectDbtRunner()

        manifest = Mock(spec=Manifest)
        upstream_node = Mock(spec=ManifestNode)
        upstream_node.relation_name = None  # Missing relation name

        manifest_node = Mock(spec=ManifestNode)
        manifest_node.depends_on_nodes = ["upstream_node_id"]

        manifest.nodes = {"upstream_node_id": upstream_node}
        runner._manifest = manifest

        with pytest.raises(ValueError, match="Relation name not found in manifest"):
            runner._get_upstream_manifest_nodes(manifest_node)

    def test_get_compiled_code_path(self) -> None:
        """Test getting compiled code path"""
        runner = PrefectDbtRunner()
        runner._project_dir = Path("/test/project")
        runner._target_path = Path("target")

        manifest_node = Mock(spec=ManifestNode)
        manifest_node.original_file_path = "models/test_model.sql"

        result = runner._get_compiled_code_path(manifest_node)
        expected = Path("/test/project/target/compiled/project/models/test_model.sql")
        assert result == expected

    @patch("builtins.open")
    @patch("os.path.exists")
    def test_get_compiled_code_enabled_and_exists(
        self, mock_exists: Mock, mock_open: Mock
    ) -> None:
        """Test getting compiled code when enabled and file exists"""
        runner = PrefectDbtRunner(include_compiled_code=True)

        # Mock that the file exists
        mock_exists.return_value = True

        mock_file = Mock()
        mock_file.read.return_value = "SELECT * FROM test"
        mock_open.return_value.__enter__.return_value = mock_file

        with patch.object(runner, "_get_compiled_code_path") as mock_path:
            mock_path.return_value = Path("/test/compiled.sql")

            manifest_node = Mock(spec=ManifestNode)
            result = runner._get_compiled_code(manifest_node)

            expected = "\n ### Compiled code\n```sql\nSELECT * FROM test\n```"
            assert result == expected

    def test_get_compiled_code_disabled(self) -> None:
        """Test getting compiled code when disabled"""
        runner = PrefectDbtRunner(include_compiled_code=False)
        manifest_node = Mock(spec=ManifestNode)

        result = runner._get_compiled_code(manifest_node)
        assert result == ""

    @patch("os.path.exists")
    def test_get_compiled_code_file_not_exists(self, mock_exists: Mock) -> None:
        """Test getting compiled code when file doesn't exist"""
        runner = PrefectDbtRunner(include_compiled_code=True)
        mock_exists.return_value = False

        manifest_node = Mock(spec=ManifestNode)
        manifest_node.original_file_path = "models/test_model.sql"
        result = runner._get_compiled_code(manifest_node)
        assert result == ""

    def test_create_asset_from_node(self) -> None:
        """Test creating asset from manifest node"""
        runner = PrefectDbtRunner()

        manifest_node = Mock(spec=ManifestNode)
        manifest_node.relation_name = "test_table"
        manifest_node.name = "test_model"
        manifest_node.description = "Test description"
        manifest_node.config = Mock()
        manifest_node.config.meta = {"owner": "test_owner"}

        with patch.object(runner, "_get_compiled_code", return_value=""):
            result = runner._create_asset_from_node(manifest_node, "postgres")

            assert result.key == "postgres://test_table"
            assert result.properties.name == "test_model"
            assert result.properties.description == "Test description"
            assert result.properties.owners == ["test_owner"]

    def test_create_asset_from_node_missing_relation_name(self) -> None:
        """Test creating asset when relation name is missing"""
        runner = PrefectDbtRunner()

        manifest_node = Mock(spec=ManifestNode)
        manifest_node.relation_name = None

        with pytest.raises(ValueError, match="Relation name not found in manifest"):
            runner._create_asset_from_node(manifest_node, "postgres")

    def test_create_task_options(self) -> None:
        """Test creating task options"""
        runner = PrefectDbtRunner()

        manifest_node = Mock(spec=ManifestNode)
        manifest_node.resource_type = "model"
        manifest_node.name = "test_model"
        manifest_node.unique_id = "model.test.test_model"

        upstream_assets = [Mock()]

        result = runner._create_task_options(manifest_node, upstream_assets)

        # TaskOptions is a dict-like object, so we access it differently
        assert result["task_run_name"] == "model test_model"
        assert result["asset_deps"] == upstream_assets

    def test_get_manifest_node_and_config(self) -> None:
        """Test getting manifest node and config"""
        runner = PrefectDbtRunner()

        manifest_node = Mock(spec=ManifestNode)
        manifest_node.config = Mock()
        manifest_node.config.meta = {"prefect": {"test": "config"}}

        manifest = Mock(spec=Manifest)
        manifest.nodes = {"test_node": manifest_node}
        runner._manifest = manifest

        node, config = runner._get_manifest_node_and_config("test_node")

        assert node == manifest_node
        assert config == {"test": "config"}

    def test_get_manifest_node_and_config_not_found(self) -> None:
        """Test getting manifest node when not found"""
        runner = PrefectDbtRunner()

        manifest = Mock(spec=Manifest)
        manifest.nodes = {}
        runner._manifest = manifest

        node, config = runner._get_manifest_node_and_config("nonexistent_node")

        assert node is None
        assert config == {}

    def test_get_dbt_event_msg(self) -> None:
        """Test extracting message from dbt event"""
        event = Mock(spec=EventMsg)
        event.info = Mock()
        event.info.msg = "Test message"

        result = PrefectDbtRunner.get_dbt_event_msg(event)
        assert result == "Test message"

    def test_get_dbt_event_node_id(self) -> None:
        """Test extracting node ID from dbt event"""
        runner = PrefectDbtRunner()

        event = Mock(spec=EventMsg)
        event.data = Mock()
        event.data.node_info = Mock()
        event.data.node_info.unique_id = "test_node_id"

        result = runner._get_dbt_event_node_id(event)
        assert result == "test_node_id"

    def test_extract_flag_value_found(self) -> None:
        """Test extracting flag value when found"""
        runner = PrefectDbtRunner()
        args = ["--target-path", "/custom/path", "run"]

        result_args, value = runner._extract_flag_value(args, "--target-path")

        assert result_args == ["run"]
        assert value == "/custom/path"

    def test_extract_flag_value_not_found(self) -> None:
        """Test extracting flag value when not found"""
        runner = PrefectDbtRunner()
        args = ["run"]

        result_args, value = runner._extract_flag_value(args, "--target-path")

        assert result_args == ["run"]
        assert value is None

    def test_update_setting_from_kwargs(self) -> None:
        """Test updating setting from kwargs"""
        runner = PrefectDbtRunner()
        kwargs = {"target_path": "/custom/path"}

        runner._update_setting_from_kwargs("target_path", kwargs)

        assert runner._target_path == "/custom/path"
        assert "target_path" not in kwargs  # Should be removed

    def test_update_setting_from_kwargs_with_converter(self) -> None:
        """Test updating setting from kwargs with converter"""
        runner = PrefectDbtRunner()
        kwargs = {"target_path": "/custom/path"}

        runner._update_setting_from_kwargs("target_path", kwargs, Path)

        assert runner._target_path == Path("/custom/path")

    def test_update_setting_from_cli_flag(self) -> None:
        """Test updating setting from CLI flag"""
        runner = PrefectDbtRunner()
        args = ["--target-path", "/custom/path", "run"]

        result_args = runner._update_setting_from_cli_flag(
            args, "--target-path", "target_path", Path
        )

        assert result_args == ["run"]
        assert runner._target_path == Path("/custom/path")

    @patch("prefect_dbt.core.runner.dbtRunner")
    def test_invoke_success(self, mock_dbt_runner: Mock) -> None:
        """Test successful dbt invoke"""
        runner = PrefectDbtRunner()

        mock_result = Mock()
        mock_result.success = True
        mock_result.exception = None

        mock_dbt_runner_instance = Mock()
        mock_dbt_runner_instance.invoke.return_value = mock_result
        mock_dbt_runner.return_value = mock_dbt_runner_instance

        with (
            patch.object(runner, "_create_logging_callback"),
            patch.object(runner, "_create_node_started_callback"),
            patch.object(runner, "_create_node_finished_callback"),
        ):
            result = runner.invoke(["run"])

            assert result == mock_result
            mock_dbt_runner_instance.invoke.assert_called_once()

    @patch("prefect_dbt.core.runner.dbtRunner")
    def test_invoke_with_exception(self, mock_dbt_runner: Mock) -> None:
        """Test dbt invoke with exception"""
        runner = PrefectDbtRunner()

        mock_result = Mock()
        mock_result.success = False
        mock_result.exception = "Test exception"

        mock_dbt_runner_instance = Mock()
        mock_dbt_runner_instance.invoke.return_value = mock_result
        mock_dbt_runner.return_value = mock_dbt_runner_instance

        with (
            patch.object(runner, "_create_logging_callback"),
            patch.object(runner, "_create_node_started_callback"),
            patch.object(runner, "_create_node_finished_callback"),
        ):
            with pytest.raises(ValueError, match="Failed to invoke dbt command"):
                runner.invoke(["run"])

    @patch("prefect_dbt.core.runner.dbtRunner")
    def test_invoke_with_failures_raise_on_failure_true(
        self, mock_dbt_runner: Mock
    ) -> None:
        """Test dbt invoke with failures when raise_on_failure is True"""
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
        mock_dbt_runner.return_value = mock_dbt_runner_instance

        with (
            patch.object(runner, "_create_logging_callback"),
            patch.object(runner, "_create_node_started_callback"),
            patch.object(runner, "_create_node_finished_callback"),
        ):
            with pytest.raises(ValueError, match="Failures detected"):
                runner.invoke(["run"])

    @patch("prefect_dbt.core.runner.dbtRunner")
    def test_invoke_with_failures_raise_on_failure_false(
        self, mock_dbt_runner: Mock
    ) -> None:
        """Test dbt invoke with failures when raise_on_failure is False"""
        runner = PrefectDbtRunner(raise_on_failure=False)

        mock_result = Mock()
        mock_result.success = False
        mock_result.exception = None

        mock_dbt_runner_instance = Mock()
        mock_dbt_runner_instance.invoke.return_value = mock_result
        mock_dbt_runner.return_value = mock_dbt_runner_instance

        with (
            patch.object(runner, "_create_logging_callback"),
            patch.object(runner, "_create_node_started_callback"),
            patch.object(runner, "_create_node_finished_callback"),
        ):
            result = runner.invoke(["run"])
            assert result == mock_result

    def test_invoke_with_kwargs_and_cli_flags(self) -> None:
        """Test invoke with both kwargs and CLI flags"""
        runner = PrefectDbtRunner()

        with (
            patch.object(runner, "_update_setting_from_kwargs") as mock_kwargs,
            patch.object(runner, "_update_setting_from_cli_flag") as mock_cli,
            patch("prefect_dbt.core.runner.dbtRunner") as mock_dbt_runner,
        ):
            mock_cli.return_value = ["run"]
            mock_dbt_runner_instance = Mock()
            mock_dbt_runner_instance.invoke.return_value = Mock(
                success=True, exception=None
            )
            mock_dbt_runner.return_value = mock_dbt_runner_instance

            with (
                patch.object(runner, "_create_logging_callback"),
                patch.object(runner, "_create_node_started_callback"),
                patch.object(runner, "_create_node_finished_callback"),
            ):
                runner.invoke(
                    ["--target-path", "/cli/path", "run"], target_path="/kwargs/path"
                )

                # Verify kwargs were processed
                mock_kwargs.assert_called()
                # Verify CLI flags were processed
                mock_cli.assert_called()


class TestExecuteDbtNode:
    """Test cases for execute_dbt_node function"""

    def test_execute_dbt_node_success(self) -> None:
        """Test successful node execution"""
        task_state = Mock(spec=TaskState)
        node_id = "test_node"
        asset_id = "test_asset"

        # Mock successful completion
        task_state.get_node_status.return_value = {
            "event_data": {"node_info": {"node_status": RunStatus.Success}}
        }

        with patch("prefect_dbt.core.runner.get_run_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            execute_dbt_node(task_state, node_id, asset_id)

            task_state.set_task_logger.assert_called_once_with(node_id, mock_logger)
            task_state.wait_for_node_completion.assert_called_once_with(node_id)
            task_state.get_node_status.assert_called_once_with(node_id)

    def test_execute_dbt_node_failure(self) -> None:
        """Test node execution with failure status"""
        task_state = Mock(spec=TaskState)
        node_id = "test_node"
        asset_id = "test_asset"

        # Mock failure status
        task_state.get_node_status.return_value = {
            "event_data": {"node_info": {"node_status": RunStatus.Error}}
        }

        with patch("prefect_dbt.core.runner.get_run_logger"):
            with pytest.raises(
                Exception, match="Node test_node finished with status error"
            ):
                execute_dbt_node(task_state, node_id, asset_id)

    def test_execute_dbt_node_no_status(self) -> None:
        """Test node execution when no status is returned"""
        task_state = Mock(spec=TaskState)
        node_id = "test_node"
        asset_id = "test_asset"

        # Mock no status returned
        task_state.get_node_status.return_value = None

        with patch("prefect_dbt.core.runner.get_run_logger"):
            execute_dbt_node(task_state, node_id, asset_id)

            task_state.set_task_logger.assert_called_once()
            task_state.wait_for_node_completion.assert_called_once_with(node_id)
            task_state.get_node_status.assert_called_once_with(node_id)


class TestConstants:
    """Test cases for module constants"""

    def test_failure_statuses(self) -> None:
        """Test that all expected failure statuses are included"""
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

    def test_materialization_node_types(self) -> None:
        """Test materialization node types"""
        from dbt.artifacts.resources.types import NodeType

        expected_types = [NodeType.Model, NodeType.Seed, NodeType.Snapshot]

        for node_type in expected_types:
            assert node_type in MATERIALIZATION_NODE_TYPES

    def test_reference_node_types(self) -> None:
        """Test reference node types"""
        from dbt.artifacts.resources.types import NodeType

        expected_types = [NodeType.Exposure, NodeType.Source]

        for node_type in expected_types:
            assert node_type in REFERENCE_NODE_TYPES
