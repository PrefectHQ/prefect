import logging
from pathlib import Path
from unittest.mock import ANY, Mock, patch

import pytest
from dbt.artifacts.resources.types import NodeType
from dbt.artifacts.schemas.catalog import CatalogArtifact
from dbt.artifacts.schemas.results import RunStatus, TestStatus
from dbt.artifacts.schemas.run import RunExecutionResult
from dbt.cli.main import dbtRunnerResult
from dbt.contracts.graph.manifest import Manifest
from dbt.contracts.graph.nodes import ManifestNode
from dbt_common.events.base_types import EventLevel
from prefect_dbt.core.runner import PrefectDbtRunner
from prefect_dbt.core.settings import PrefectDbtSettings

from prefect import flow
from prefect.events.schemas.events import RelatedResource


@pytest.fixture
def mock_dbt_runner():
    with patch("prefect_dbt.core.runner.dbtRunner") as mock_runner:
        mock_instance = Mock()
        mock_runner.return_value = mock_instance

        # Setup default successful result
        result = Mock(spec=dbtRunnerResult)
        result.success = True
        # Create a Mock that inherits from Manifest
        manifest_mock = Mock(spec=Manifest)
        manifest_mock.metadata = Mock()
        manifest_mock.metadata.adapter_type = "postgres"
        result.result = manifest_mock
        mock_instance.invoke.return_value = result

        yield mock_instance


@pytest.fixture
def settings():
    return PrefectDbtSettings(
        profiles_dir=Path("./tests/dbt_configs").resolve(),
        project_dir=Path("./tests/dbt_configs").resolve(),
        log_level=EventLevel.DEBUG,
    )


@pytest.fixture
def mock_manifest():
    """Create a mock manifest with different node types."""
    manifest = Mock(spec=Manifest)
    # Create the metadata structure
    manifest.metadata = Mock()
    manifest.metadata.adapter_type = "postgres"
    return manifest


@pytest.fixture
def mock_nodes():
    """Create mock nodes of different types."""
    model_node = Mock()
    model_node.relation_name = '"schema"."model_table"'
    model_node.depends_on_nodes = []
    model_node.config.meta = {}
    model_node.resource_type = NodeType.Model
    model_node.unique_id = "model.test.model"
    model_node.name = "model"

    seed_node = Mock()
    seed_node.relation_name = '"schema"."seed_table"'
    seed_node.depends_on_nodes = []
    seed_node.config.meta = {}
    seed_node.resource_type = NodeType.Seed
    seed_node.unique_id = "seed.test.seed"
    seed_node.name = "seed"

    exposure_node = Mock()
    exposure_node.relation_name = '"schema"."exposure_table"'
    exposure_node.depends_on_nodes = []
    exposure_node.config.meta = {}
    exposure_node.resource_type = NodeType.Exposure
    exposure_node.unique_id = "exposure.test.exposure"
    exposure_node.name = "exposure"

    test_node = Mock()
    test_node.relation_name = '"schema"."test_table"'
    test_node.depends_on_nodes = []
    test_node.config.meta = {}
    test_node.resource_type = NodeType.Test
    test_node.unique_id = "test.test.test"
    test_node.name = "test"

    return {
        "model": model_node,
        "seed": seed_node,
        "exposure": exposure_node,
        "test": test_node,
    }


@pytest.fixture
def mock_manifest_with_nodes(mock_manifest, mock_nodes):
    """Create a mock manifest populated with test nodes."""
    mock_manifest.nodes = {
        "model.test.model": mock_nodes["model"],
        "seed.test.seed": mock_nodes["seed"],
        "exposure.test.exposure": mock_nodes["exposure"],
        "test.test.test": mock_nodes["test"],
    }
    return mock_manifest


class TestPrefectDbtRunnerInitialization:
    def test_runner_initialization(self, settings):
        manifest = Mock()
        client = Mock()

        runner = PrefectDbtRunner(manifest=manifest, settings=settings, client=client)

        assert runner.manifest == manifest
        assert runner.settings == settings
        assert runner.client == client

    def test_runner_default_initialization(self):
        runner = PrefectDbtRunner()

        assert runner.manifest is None
        assert isinstance(runner.settings, PrefectDbtSettings)
        assert runner.client is not None


class TestPrefectDbtRunnerParse:
    def test_parse_success(self, mock_dbt_runner, settings):
        runner = PrefectDbtRunner(settings=settings)
        runner.parse()

        mock_dbt_runner.invoke.assert_called_once_with(
            ["parse"],
            profiles_dir=ANY,
            project_dir=settings.project_dir,
            log_level=EventLevel.DEBUG,
        )
        assert runner.manifest is not None

    def test_parse_failure(self, mock_dbt_runner, settings):
        mock_dbt_runner.invoke.return_value.success = False
        mock_dbt_runner.invoke.return_value.exception = "Parse error"

        runner = PrefectDbtRunner(settings=settings)

        with pytest.raises(ValueError, match="Failed to load manifest"):
            runner.parse()


class TestPrefectDbtRunnerInvoke:
    # Basic invocation tests
    def test_invoke_with_custom_kwargs(self, mock_dbt_runner, settings):
        runner = PrefectDbtRunner(settings=settings)

        runner.invoke(["run"], vars={"custom_var": "value"}, threads=4)

        call_kwargs = mock_dbt_runner.invoke.call_args.kwargs
        assert call_kwargs["vars"] == {"custom_var": "value"}
        assert call_kwargs["threads"] == 4
        assert call_kwargs["profiles_dir"] == ANY
        assert call_kwargs["project_dir"] == settings.project_dir

    @pytest.mark.asyncio
    async def test_ainvoke_with_custom_kwargs(self, mock_dbt_runner, settings):
        runner = PrefectDbtRunner(settings=settings)

        await runner.ainvoke(["run"], vars={"custom_var": "value"}, threads=4)

        call_kwargs = mock_dbt_runner.invoke.call_args.kwargs
        assert call_kwargs["vars"] == {"custom_var": "value"}
        assert call_kwargs["threads"] == 4
        assert call_kwargs["profiles_dir"] == ANY
        assert call_kwargs["project_dir"] == settings.project_dir

    # Parsing tests
    def test_invoke_with_parsing(self, mock_dbt_runner, settings):
        runner = PrefectDbtRunner(settings=settings)

        runner.invoke(["run"])

        assert mock_dbt_runner.invoke.call_count == 2
        parse_call = mock_dbt_runner.invoke.call_args_list[0]
        assert parse_call.args[0] == ["parse"]

        run_call = mock_dbt_runner.invoke.call_args_list[1]
        assert run_call.args[0] == ["run"]

    @pytest.mark.asyncio
    async def test_ainvoke_with_parsing(self, mock_dbt_runner, settings):
        runner = PrefectDbtRunner(settings=settings)

        await runner.ainvoke(["run"])

        assert mock_dbt_runner.invoke.call_count == 2
        parse_call = mock_dbt_runner.invoke.call_args_list[0]
        assert parse_call.args[0] == ["parse"]

        run_call = mock_dbt_runner.invoke.call_args_list[1]
        assert run_call.args[0] == ["run"]

    # Single failure tests
    def test_invoke_raises_on_failure(self, mock_dbt_runner, settings):
        runner = PrefectDbtRunner(settings=settings)

        # Setup successful parse result first
        parse_result = Mock(spec=dbtRunnerResult)
        parse_result.success = True
        manifest_mock = Mock(Manifest)
        parse_result.result = manifest_mock

        # Mock a failed run result
        run_result = Mock(spec=dbtRunnerResult)
        run_result.success = False
        run_result.exception = None
        run_result.result = Mock(spec=RunExecutionResult)

        # Create a failed node result
        node_result = Mock()
        node_result.status = RunStatus.Error
        node_result.node.resource_type = NodeType.Model
        node_result.node.name = "failed_model"
        node_result.message = "Something went wrong"

        run_result.result.results = [node_result]

        # Set up the side effects to return parse_result for parse command and run_result for run command
        def side_effect(args, **kwargs):
            if args == ["parse"]:
                return parse_result
            elif args == ["run"]:
                return run_result
            return Mock()

        mock_dbt_runner.invoke.side_effect = side_effect

        with pytest.raises(
            ValueError, match="Failures detected during invocation of dbt command 'run'"
        ):
            runner.invoke(["run"])

    @pytest.mark.asyncio
    async def test_ainvoke_raises_on_failure(self, mock_dbt_runner, settings):
        runner = PrefectDbtRunner(settings=settings)

        # Setup successful parse result first
        parse_result = Mock(spec=dbtRunnerResult)
        parse_result.success = True
        manifest_mock = Mock(Manifest)
        parse_result.result = manifest_mock

        # Mock a failed result
        run_result = Mock(spec=dbtRunnerResult)
        run_result.success = False
        run_result.exception = None
        run_result.result = Mock(spec=RunExecutionResult)
        # Create a failed node result
        node_result = Mock()
        node_result.status = RunStatus.Error
        node_result.node.resource_type = NodeType.Model
        node_result.node.name = "failed_model"
        node_result.message = "Something went wrong"

        run_result.result.results = [node_result]

        def side_effect(args, **kwargs):
            if args == ["parse"]:
                return parse_result
            elif args == ["run"]:
                return run_result
            return Mock()

        mock_dbt_runner.invoke.side_effect = side_effect

        with pytest.raises(
            ValueError, match="Failures detected during invocation of dbt command 'run'"
        ):
            await runner.ainvoke(["run"])

    # Multiple failures tests
    def test_invoke_multiple_failures(self, mock_dbt_runner, settings):
        runner = PrefectDbtRunner(settings=settings)

        # Setup successful parse result first
        parse_result = Mock(spec=dbtRunnerResult)
        parse_result.success = True
        manifest_mock = Mock(Manifest)
        parse_result.result = manifest_mock

        # Mock a failed result with multiple failures
        run_result = Mock(spec=dbtRunnerResult)
        run_result.success = False
        run_result.exception = None
        run_result.result = Mock(spec=RunExecutionResult)

        # Create multiple failed node results
        failed_model = Mock()
        failed_model.status = RunStatus.Error
        failed_model.node.resource_type = NodeType.Model
        failed_model.node.name = "failed_model"
        failed_model.message = "Model error"

        failed_test = Mock()
        failed_test.status = TestStatus.Fail
        failed_test.node.resource_type = NodeType.Test
        failed_test.node.name = "failed_test"
        failed_test.message = "Test failed"

        run_result.result.results = [failed_model, failed_test]

        def side_effect(args, **kwargs):
            if args == ["parse"]:
                return parse_result
            elif args == ["run"]:
                return run_result
            return Mock()

        mock_dbt_runner.invoke.side_effect = side_effect

        with pytest.raises(ValueError) as exc_info:
            runner.invoke(["run"])

        error_message = str(exc_info.value)
        assert 'Model failed_model errored with message: "Model error"' in error_message
        assert 'Test failed_test failed with message: "Test failed"' in error_message

    @pytest.mark.asyncio
    async def test_ainvoke_multiple_failures(self, mock_dbt_runner, settings):
        runner = PrefectDbtRunner(settings=settings)

        # Setup successful parse result first
        parse_result = Mock(spec=dbtRunnerResult)
        parse_result.success = True
        manifest_mock = Mock(Manifest)
        parse_result.result = manifest_mock

        # Mock a failed result with multiple failures
        run_result = Mock(spec=dbtRunnerResult)
        run_result.success = False
        run_result.exception = None
        run_result.result = Mock(spec=RunExecutionResult)

        # Create multiple failed node results
        failed_model = Mock()
        failed_model.status = RunStatus.Error
        failed_model.node.resource_type = NodeType.Model
        failed_model.node.name = "failed_model"
        failed_model.message = "Model error"

        failed_test = Mock()
        failed_test.status = TestStatus.Fail
        failed_test.node.resource_type = NodeType.Test
        failed_test.node.name = "failed_test"
        failed_test.message = "Test failed"

        run_result.result.results = [failed_model, failed_test]

        def side_effect(args, **kwargs):
            if args == ["parse"]:
                return parse_result
            elif args == ["run"]:
                return run_result
            return Mock()

        mock_dbt_runner.invoke.side_effect = side_effect

        with pytest.raises(ValueError) as exc_info:
            await runner.ainvoke(["run"])

        error_message = str(exc_info.value)
        assert 'Model failed_model errored with message: "Model error"' in error_message
        assert 'Test failed_test failed with message: "Test failed"' in error_message

    # No raise on failure tests
    def test_invoke_no_raise_on_failure(self, mock_dbt_runner, settings):
        runner = PrefectDbtRunner(settings=settings, raise_on_failure=False)

        # Setup successful parse result first
        parse_result = Mock(spec=dbtRunnerResult)
        parse_result.success = True
        manifest_mock = Mock(Manifest)
        parse_result.result = manifest_mock

        # Mock a failed result
        run_result = Mock(spec=dbtRunnerResult)
        run_result.success = False
        run_result.exception = None

        # Create a failed node result
        node_result = Mock()
        node_result.status = RunStatus.Error
        node_result.node.resource_type = NodeType.Model
        node_result.node.name = "failed_model"
        node_result.message = "Something went wrong"

        run_result.result.results = [node_result]

        def side_effect(args, **kwargs):
            if args == ["parse"]:
                return parse_result
            elif args == ["run"]:
                return run_result
            return Mock()

        mock_dbt_runner.invoke.side_effect = side_effect

        # Should not raise an exception
        result = runner.invoke(["run"])
        assert result.success is False

    @pytest.mark.asyncio
    async def test_ainvoke_no_raise_on_failure(self, mock_dbt_runner, settings):
        runner = PrefectDbtRunner(settings=settings, raise_on_failure=False)

        # Setup successful parse result first
        parse_result = Mock(spec=dbtRunnerResult)
        parse_result.success = True
        manifest_mock = Mock(Manifest)
        parse_result.result = manifest_mock

        # Mock a failed result
        run_result = Mock(spec=dbtRunnerResult)
        run_result.success = False
        run_result.exception = None

        # Create a failed node result
        node_result = Mock()
        node_result.status = RunStatus.Error
        node_result.node.resource_type = NodeType.Model
        node_result.node.name = "failed_model"
        node_result.message = "Something went wrong"

        run_result.result.results = [node_result]

        def side_effect(args, **kwargs):
            if args == ["parse"]:
                return parse_result
            elif args == ["run"]:
                return run_result
            return Mock()

        mock_dbt_runner.invoke.side_effect = side_effect

        # Should not raise an exception
        result = await runner.ainvoke(["run"])
        assert result.success is False

    @pytest.mark.parametrize(
        "command,expected_type,requires_manifest",
        [
            (["run"], RunExecutionResult, True),
            (["test"], RunExecutionResult, True),
            (["seed"], RunExecutionResult, True),
            (["snapshot"], RunExecutionResult, True),
            (["build"], RunExecutionResult, True),
            (["compile"], RunExecutionResult, True),
            (["run-operation"], RunExecutionResult, True),
            (["parse"], Manifest, False),
            (["docs", "generate"], CatalogArtifact, True),
            (["list"], list, True),
            (["ls"], list, True),
            (["debug"], bool, False),
            (["clean"], None, False),
            (["deps"], None, False),
            (["init"], None, False),
            (["source"], None, True),
        ],
    )
    def test_invoke_command_return_types(
        self, mock_dbt_runner, settings, command, expected_type, requires_manifest
    ):
        """Test that different dbt commands return the expected result types."""
        runner = PrefectDbtRunner(settings=settings)

        # Mock parse result if needed
        parse_result = Mock(spec=dbtRunnerResult)
        parse_result.success = True
        manifest = Mock(spec=Manifest)  # Create the manifest
        manifest.metadata = Mock()  # Add required metadata
        manifest.metadata.adapter_type = "postgres"
        parse_result.result = manifest  # Set the actual manifest

        # Mock command result
        command_result = Mock(spec=dbtRunnerResult)
        command_result.success = True
        command_result.exception = None

        # Set appropriate result based on command
        if expected_type is None:
            command_result.result = None
        elif expected_type is bool:
            command_result.result = True
        elif expected_type is list:
            command_result.result = ["item1", "item2"]
        else:
            command_result.result = Mock(spec=expected_type)

        def side_effect(args, **kwargs):
            if args == ["parse"]:
                return parse_result
            return command_result

        mock_dbt_runner.invoke.side_effect = side_effect

        result = runner.invoke(command)

        assert result.success
        if expected_type is None:
            assert result.result is None
        elif expected_type is bool:
            assert isinstance(result.result, bool)
        elif expected_type is list:
            assert isinstance(result.result, list)
            assert all(isinstance(item, str) for item in result.result)
        else:
            assert isinstance(result.result, expected_type)

        # Verify call count and order
        if requires_manifest:
            assert mock_dbt_runner.invoke.call_count == 2
            assert mock_dbt_runner.invoke.call_args_list[0].args[0] == ["parse"]
            assert mock_dbt_runner.invoke.call_args_list[1].args[0] == command
        else:
            mock_dbt_runner.invoke.assert_called_once()
            assert mock_dbt_runner.invoke.call_args.args[0] == command

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "command,expected_type,requires_manifest",
        [
            (["run"], RunExecutionResult, True),
            (["test"], RunExecutionResult, True),
            (["seed"], RunExecutionResult, True),
            (["snapshot"], RunExecutionResult, True),
            (["build"], RunExecutionResult, True),
            (["compile"], RunExecutionResult, True),
            (["run-operation"], RunExecutionResult, True),
            (["parse"], Manifest, False),
            (["docs", "generate"], CatalogArtifact, True),
            (["list"], list, True),
            (["ls"], list, True),
            (["debug"], bool, False),
            (["clean"], None, False),
            (["deps"], None, False),
            (["init"], None, False),
            (["source"], None, True),
        ],
    )
    async def test_ainvoke_command_return_types(
        self, mock_dbt_runner, settings, command, expected_type, requires_manifest
    ):
        """Test that different dbt commands return the expected result types when called asynchronously."""
        runner = PrefectDbtRunner(settings=settings)

        # Mock parse result if needed
        parse_result = Mock(spec=dbtRunnerResult)
        parse_result.success = True
        parse_result.result = Mock(spec=Manifest)

        # Mock command result
        command_result = Mock(spec=dbtRunnerResult)
        command_result.success = True
        command_result.exception = None

        # Set appropriate result based on command
        if expected_type is None:
            command_result.result = None
        elif expected_type is bool:
            command_result.result = True
        elif expected_type is list:
            command_result.result = ["item1", "item2"]
        else:
            command_result.result = Mock(spec=expected_type)

        def side_effect(args, **kwargs):
            if args == ["parse"]:
                return parse_result
            return command_result

        mock_dbt_runner.invoke.side_effect = side_effect

        result = await runner.ainvoke(command)

        assert result.success
        if expected_type is None:
            assert result.result is None
        elif expected_type is bool:
            assert isinstance(result.result, bool)
        elif expected_type is list:
            assert isinstance(result.result, list)
            assert all(isinstance(item, str) for item in result.result)
        else:
            assert isinstance(result.result, expected_type)

        # Verify call count and order
        if requires_manifest:
            assert mock_dbt_runner.invoke.call_count == 2
            assert mock_dbt_runner.invoke.call_args_list[0].args[0] == ["parse"]
            assert mock_dbt_runner.invoke.call_args_list[1].args[0] == command
        else:
            mock_dbt_runner.invoke.assert_called_once()
            assert mock_dbt_runner.invoke.call_args.args[0] == command

    def test_invoke_with_manifest_requiring_commands(self, mock_dbt_runner, settings):
        """Test that commands requiring manifest trigger parse if manifest not provided."""
        runner = PrefectDbtRunner(settings=settings)

        # Mock parse result
        parse_result = Mock(spec=dbtRunnerResult)
        parse_result.success = True
        parse_result.result = Mock(spec=Manifest)

        # Mock run result
        run_result = Mock(spec=dbtRunnerResult)
        run_result.success = True
        run_result.result = Mock(spec=RunExecutionResult)

        def side_effect(args, **kwargs):
            if args == ["parse"]:
                return parse_result
            return run_result

        mock_dbt_runner.invoke.side_effect = side_effect

        # Test with command that requires manifest
        runner.invoke(["run"])
        assert mock_dbt_runner.invoke.call_count == 2
        assert mock_dbt_runner.invoke.call_args_list[0].args[0] == ["parse"]
        assert mock_dbt_runner.invoke.call_args_list[1].args[0] == ["run"]

        # Reset mock
        mock_dbt_runner.invoke.reset_mock()
        mock_dbt_runner.invoke.side_effect = side_effect

        # Test with command that doesn't require manifest
        runner.invoke(["clean"])
        assert mock_dbt_runner.invoke.call_count == 1
        assert mock_dbt_runner.invoke.call_args_list[0].args[0] == ["clean"]

    def test_invoke_with_preloaded_manifest(self, mock_dbt_runner, settings):
        """Test that commands don't trigger parse when manifest is preloaded."""
        manifest = Mock(spec=Manifest)
        runner = PrefectDbtRunner(settings=settings, manifest=manifest)

        # Mock run result
        run_result = Mock(spec=dbtRunnerResult)
        run_result.success = True
        run_result.result = Mock(spec=RunExecutionResult)
        mock_dbt_runner.invoke.return_value = run_result

        # Test with command that normally requires manifest
        runner.invoke(["run"])

        # Should not call parse since manifest was preloaded
        mock_dbt_runner.invoke.assert_called_once()
        assert mock_dbt_runner.invoke.call_args.args[0] == ["run"]

    def test_invoke_debug_command(self, mock_dbt_runner, settings):
        """Test the dbt debug command which has unique behavior."""
        runner = PrefectDbtRunner(settings=settings)

        # Mock debug result
        debug_result = Mock(spec=dbtRunnerResult)
        debug_result.success = True
        # debug command doesn't return a specific result type
        debug_result.result = None
        mock_dbt_runner.invoke.return_value = debug_result

        result = runner.invoke(["debug"])

        assert result.success
        assert result.result is None
        mock_dbt_runner.invoke.assert_called_once_with(
            ["debug"],
            project_dir=settings.project_dir,
            profiles_dir=ANY,
            log_level=ANY,
        )

    @pytest.mark.parametrize(
        "command,expected_type",
        [
            (["run"], RunExecutionResult),
            (["test"], RunExecutionResult),
            (["seed"], RunExecutionResult),
            (["snapshot"], RunExecutionResult),
            (["build"], RunExecutionResult),
            (["compile"], RunExecutionResult),
            (["run-operation"], RunExecutionResult),
            (["parse"], Manifest),
            (["docs", "generate"], CatalogArtifact),
            (["list"], list),
            (["ls"], list),
            (["debug"], bool),
            (["clean"], type(None)),
            (["deps"], type(None)),
            (["init"], type(None)),
            (["source"], type(None)),
        ],
    )
    def test_failure_result_types(
        self, mock_dbt_runner, settings, command, expected_type
    ):
        """Test that failed commands return the expected result types."""
        runner = PrefectDbtRunner(settings=settings, raise_on_failure=False)

        # Mock parse result if needed for manifest loading
        parse_result = Mock(spec=dbtRunnerResult)
        parse_result.success = True
        manifest = Mock(spec=Manifest)
        manifest.metadata = Mock()
        manifest.metadata.adapter_type = "postgres"
        parse_result.result = manifest

        # Mock failed command result
        command_result = Mock(spec=dbtRunnerResult)
        command_result.success = False
        command_result.exception = None

        # Set appropriate result based on command
        if expected_type is type(None):
            command_result.result = None
        elif expected_type is bool:
            command_result.result = False
        elif expected_type is list:
            command_result.result = []
        else:
            command_result.result = Mock(spec=expected_type)
            if expected_type == RunExecutionResult:
                # Add failed results for RunExecutionResult
                failed_node = Mock()
                failed_node.status = RunStatus.Error
                failed_node.node = Mock()
                failed_node.node.resource_type = NodeType.Model
                failed_node.node.name = "failed_model"
                failed_node.message = "Test failure"
                command_result.result.results = [failed_node]

        def side_effect(args, **kwargs):
            if args == ["parse"] and command != [
                "parse"
            ]:  # Only return successful parse when loading manifest
                return parse_result
            return command_result

        mock_dbt_runner.invoke.side_effect = side_effect

        result = runner.invoke(command)

        assert not result.success
        if expected_type is type(None):
            assert result.result is None
        else:
            assert isinstance(result.result, expected_type)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "command,expected_type",
        [
            (["run"], RunExecutionResult),
            (["test"], RunExecutionResult),
            (["seed"], RunExecutionResult),
            (["snapshot"], RunExecutionResult),
            (["build"], RunExecutionResult),
            (["compile"], RunExecutionResult),
            (["run-operation"], RunExecutionResult),
            (["parse"], Manifest),
            (["docs", "generate"], CatalogArtifact),
            (["list"], list),
            (["ls"], list),
            (["debug"], bool),
            (["clean"], type(None)),
            (["deps"], type(None)),
            (["init"], type(None)),
            (["source"], type(None)),
        ],
    )
    async def test_failure_result_types_async(
        self, mock_dbt_runner, settings, command, expected_type
    ):
        """Test that failed commands return the expected result types when called asynchronously."""
        runner = PrefectDbtRunner(settings=settings, raise_on_failure=False)

        # Mock parse result if needed for manifest loading
        parse_result = Mock(spec=dbtRunnerResult)
        parse_result.success = True
        manifest = Mock(spec=Manifest)
        parse_result.result = manifest

        # Mock failed command result
        command_result = Mock(spec=dbtRunnerResult)
        command_result.success = False
        command_result.exception = None

        # Set appropriate result based on command
        if expected_type is type(None):
            command_result.result = None
        elif expected_type is bool:
            command_result.result = False
        elif expected_type is list:
            command_result.result = []
        else:
            command_result.result = Mock(spec=expected_type)
            if expected_type == RunExecutionResult:
                # Add failed results for RunExecutionResult
                failed_node = Mock()
                failed_node.status = RunStatus.Error
                failed_node.node = Mock()
                failed_node.node.resource_type = NodeType.Model
                failed_node.node.name = "failed_model"
                failed_node.message = "Test failure"
                command_result.result.results = [failed_node]

        def side_effect(args, **kwargs):
            if args == ["parse"] and command != [
                "parse"
            ]:  # Only return successful parse when loading manifest
                return parse_result
            return command_result

        mock_dbt_runner.invoke.side_effect = side_effect

        result = await runner.ainvoke(command)

        assert not result.success
        if expected_type is type(None):
            assert result.result is None
        else:
            assert isinstance(result.result, expected_type)


class TestPrefectDbtRunnerLogging:
    def test_logging_callback(self, mock_dbt_runner, settings, caplog):
        runner = PrefectDbtRunner(settings=settings)

        # Create mock events for different log levels
        debug_event = Mock()
        debug_event.info.level = EventLevel.DEBUG
        debug_event.info.msg = "Debug message"

        info_event = Mock()
        info_event.info.level = EventLevel.INFO
        info_event.info.msg = "Info message"

        warn_event = Mock()
        warn_event.info.level = EventLevel.WARN
        warn_event.info.msg = "Warning message"

        error_event = Mock()
        error_event.info.level = EventLevel.ERROR
        error_event.info.msg = "Error message"

        test_event = Mock()
        test_event.info.level = EventLevel.TEST
        test_event.info.msg = "Test message"

        @flow
        def test_flow():
            callback = runner._create_logging_callback(EventLevel.DEBUG)
            callback(debug_event)
            callback(info_event)
            callback(warn_event)
            callback(error_event)
            callback(test_event)

        caplog.clear()

        with caplog.at_level(logging.DEBUG):
            test_flow()

            assert "Debug message" in caplog.text
            assert "Test message" in caplog.text
            assert "Info message" in caplog.text
            assert "Warning message" in caplog.text
            assert "Error message" in caplog.text

            for record in caplog.records:
                if (
                    "Debug message" in record.message
                    or "Test message" in record.message
                ):
                    assert record.levelno == logging.DEBUG
                elif "Info message" in record.message:
                    assert record.levelno == logging.INFO
                elif "Warning message" in record.message:
                    assert record.levelno == logging.WARNING
                elif "Error message" in record.message:
                    assert record.levelno == logging.ERROR

    def test_logging_callback_no_flow(self, mock_dbt_runner, settings, caplog):
        runner = PrefectDbtRunner(settings=settings)

        event = Mock()
        event.info.level = EventLevel.INFO
        event.info.msg = "Test message"

        # no flow decorator
        def test_flow():
            callback = runner._create_logging_callback(EventLevel.DEBUG)
            callback(event)

        caplog.clear()

        with caplog.at_level(logging.INFO):
            test_flow()
            assert caplog.text == "", (
                "Expected empty log output when not in flow context"
            )


class TestPrefectDbtRunnerEvents:
    def test_events_callback_node_finished(self, mock_dbt_runner, settings):
        """Test that the events callback correctly handles NodeFinished events."""
        runner = PrefectDbtRunner(settings=settings)
        runner.manifest = Mock()
        runner.manifest.metadata.adapter_type = "postgres"

        # Create a mock node in the manifest
        node = Mock(spec=ManifestNode)
        node.unique_id = "model.test.example"
        node.name = "example"
        node.relation_name = '"schema"."example_table"'
        node.depends_on_nodes = ["model.test.upstream"]
        node.config = Mock()
        node.config.meta = {
            "prefect": {
                "upstream_resources": [
                    {
                        "id": "s3://bucket/path",
                        "role": "source",
                        "name": "upstream_s3_table",
                    },
                ]
            }
        }
        node.resource_type = NodeType.Model
        runner.manifest.nodes = {"model.test.example": node}

        # Create a mock upstream node
        upstream_node = Mock()
        upstream_node.name = "upstream"
        upstream_node.unique_id = "model.test.upstream"
        upstream_node.relation_name = '"schema"."upstream_table"'
        upstream_node.config = Mock()
        upstream_node.config.meta = {}
        upstream_node.resource_type = NodeType.Model
        runner.manifest.nodes["model.test.upstream"] = upstream_node

        # Create a mock NodeFinished event
        event = Mock()
        event.info.name = "NodeFinished"
        event.data.node_info.unique_id = "model.test.example"

        # Create mock related resources from context
        related_context = [
            RelatedResource(
                root={
                    "prefect.resource.id": "flow/123",
                    "prefect.resource.role": "flow",
                    "prefect.resource.name": "test-flow",
                }
            )
        ]

        callback = runner._create_events_callback(related_context)

        with (
            patch("prefect_dbt.core.runner.MessageToDict") as mock_to_dict,
            patch("prefect_dbt.core.runner.emit_event") as mock_emit,
            patch(
                "prefect_dbt.core.runner.emit_external_resource_lineage"
            ) as mock_emit_lineage,
        ):
            # Mock the event data dictionary
            mock_to_dict.return_value = {
                "node_info": {
                    "unique_id": "model.test.example",
                    "node_status": "success",
                }
            }

            # Call the callback
            callback(event)

            # Verify node event was emitted
            assert mock_emit.call_count == 1
            node_event_call = mock_emit.call_args_list[0]
            assert node_event_call.kwargs["event"] == "example success"
            assert node_event_call.kwargs["resource"] == {
                "prefect.resource.id": "dbt.model.test.example",
                "prefect.resource.name": "example",
                "dbt.node.status": "success",
            }
            assert any(
                r["prefect.resource.id"] == "flow/123"
                for r in node_event_call.kwargs["related"]
            )

            # Verify lineage was emitted
            assert mock_emit_lineage.call_count == 1
            lineage_call = mock_emit_lineage.call_args

            # Check context resources
            assert lineage_call.kwargs["context_resources"] == related_context

            # Check upstream resources
            upstream_resources = lineage_call.kwargs["upstream_resources"]
            assert len(upstream_resources) == 2  # One from depends_on, one from meta
            assert {
                "prefect.resource.id": "postgres://schema/upstream_table",
                "prefect.resource.lineage-group": "global",
                "prefect.resource.role": NodeType.Model,
                "prefect.resource.name": "upstream",
            } in upstream_resources
            assert {
                "prefect.resource.id": "s3://bucket/path",
                "prefect.resource.lineage-group": "global",
                "prefect.resource.role": "source",
                "prefect.resource.name": "upstream_s3_table",
            } in upstream_resources

            # Check downstream resource
            assert lineage_call.kwargs["downstream_resources"] == [
                {
                    "prefect.resource.id": "postgres://schema/example_table",
                    "prefect.resource.lineage-group": "global",
                    "prefect.resource.role": NodeType.Model,
                    "prefect.resource.name": "example",
                }
            ]

    def test_events_callback_with_emit_events_false(self, mock_dbt_runner, settings):
        runner = PrefectDbtRunner(settings=settings)
        runner.manifest = Mock()
        runner.manifest.metadata.adapter_type = "postgres"

        node = Mock()
        node.relation_name = '"schema"."table"'
        node.depends_on_nodes = []
        node.config.meta = {"prefect": {"emit_events": False}}
        node.resource_type = NodeType.Model
        runner.manifest.nodes = {"model.test.example": node}

        event = Mock()
        event.info.name = "NodeFinished"
        event.data.node_info.unique_id = "model.test.example"

        callback = runner._create_events_callback([])

        with (
            patch("prefect_dbt.core.runner.MessageToDict") as mock_to_dict,
            patch("prefect_dbt.core.runner.emit_event") as mock_emit,
        ):
            mock_to_dict.return_value = {
                "node_info": {
                    "unique_id": "model.test.example",
                    "node_status": "success",
                }
            }

            callback(event)
            mock_emit.assert_not_called()

    def test_events_callback_with_emit_node_events_false(
        self, mock_dbt_runner, settings
    ):
        """Test that when emit_node_events is False, only lineage events are emitted."""
        runner = PrefectDbtRunner(settings=settings)
        runner.manifest = Mock()
        runner.manifest.metadata.adapter_type = "postgres"

        # Create a mock node in the manifest
        node = Mock()
        node.name = "example"
        node.relation_name = '"schema"."example_table"'
        node.depends_on_nodes = []
        node.config.meta = {"prefect": {"emit_node_events": False}}
        node.resource_type = NodeType.Model
        runner.manifest.nodes = {"model.test.example": node}

        # Create a mock NodeFinished event
        event = Mock()
        event.info.name = "NodeFinished"
        event.data.node_info.unique_id = "model.test.example"

        # Create mock related resources from context
        related_context = [
            RelatedResource(
                root={
                    "prefect.resource.id": "flow/123",
                    "prefect.resource.role": "flow",
                    "prefect.resource.name": "test-flow",
                }
            )
        ]

        callback = runner._create_events_callback(related_context)

        with (
            patch("prefect_dbt.core.runner.MessageToDict") as mock_to_dict,
            patch("prefect_dbt.core.runner.emit_event") as mock_emit,
            patch(
                "prefect_dbt.core.runner.emit_external_resource_lineage"
            ) as mock_emit_lineage,
        ):
            # Mock the event data dictionary
            mock_to_dict.return_value = {
                "node_info": {
                    "unique_id": "model.test.example",
                    "node_status": "success",
                }
            }

            # Call the callback
            callback(event)

            # Verify node event was not emitted
            mock_emit.assert_not_called()

            # Verify lineage was still emitted
            assert mock_emit_lineage.call_count == 1
            lineage_call = mock_emit_lineage.call_args

            # Check context resources
            assert lineage_call.kwargs["context_resources"] == related_context

            # Check downstream resource
            assert lineage_call.kwargs["downstream_resources"] == [
                {
                    "prefect.resource.id": "postgres://schema/example_table",
                    "prefect.resource.lineage-group": "global",
                    "prefect.resource.role": NodeType.Model,
                    "prefect.resource.name": "example",
                }
            ]

    def test_events_callback_with_emit_lineage_events_false(
        self, mock_dbt_runner, settings
    ):
        runner = PrefectDbtRunner(settings=settings)
        runner.manifest = Mock()
        runner.manifest.metadata.adapter_type = "postgres"

        node = Mock()
        node.name = "example"
        node.relation_name = '"schema"."table"'
        node.depends_on_nodes = []
        node.config.meta = {"prefect": {"emit_lineage_events": False}}
        node.resource_type = NodeType.Model
        runner.manifest.nodes = {"model.test.example": node}

        event = Mock()
        event.info.name = "NodeFinished"
        event.data.node_info.unique_id = "model.test.example"

        callback = runner._create_events_callback([])

        with (
            patch("prefect_dbt.core.runner.MessageToDict") as mock_to_dict,
            patch("prefect_dbt.core.runner.emit_event") as mock_emit,
        ):
            mock_to_dict.return_value = {
                "node_info": {
                    "unique_id": "model.test.example",
                    "node_status": "success",
                }
            }

            callback(event)
            assert mock_emit.call_count == 1  # Only node event should be emitted
            assert mock_emit.call_args.kwargs["event"] == "example success"

    def test_events_callback_with_all_events_disabled(self, mock_dbt_runner, settings):
        runner = PrefectDbtRunner(settings=settings)
        runner.manifest = Mock()
        runner.manifest.metadata.adapter_type = "postgres"

        node = Mock()
        node.relation_name = '"schema"."table"'
        node.depends_on_nodes = []
        node.config.meta = {
            "prefect": {
                "emit_events": True,
                "emit_node_events": False,
                "emit_lineage_events": False,
            }
        }
        node.resource_type = NodeType.Model
        runner.manifest.nodes = {"model.test.example": node}

        event = Mock()
        event.info.name = "NodeFinished"
        event.data.node_info.unique_id = "model.test.example"

        callback = runner._create_events_callback([])

        with (
            patch("prefect_dbt.core.runner.MessageToDict") as mock_to_dict,
            patch("prefect_dbt.core.runner.emit_event") as mock_emit,
        ):
            mock_to_dict.return_value = {
                "node_info": {
                    "unique_id": "model.test.example",
                    "node_status": "success",
                }
            }

            callback(event)
            mock_emit.assert_not_called()


class TestPrefectDbtRunnerLineage:
    @pytest.mark.parametrize("provide_manifest", [True, False])
    def test_emit_lineage_events(
        self, mock_dbt_runner, settings, mock_manifest_with_nodes, provide_manifest
    ):
        """Test that lineage events are emitted correctly for all relevant nodes."""
        runner = PrefectDbtRunner(
            settings=settings,
            manifest=mock_manifest_with_nodes if provide_manifest else None,
        )

        if not provide_manifest:
            # Setup the mock to return our manifest when parse() is called
            mock_dbt_runner.invoke.return_value.result = mock_manifest_with_nodes

        @flow(flow_run_name="test-flow-name")
        def test_flow():
            with patch(
                "prefect_dbt.core.runner.emit_external_resource_lineage"
            ) as mock_emit_lineage:
                runner.emit_lineage_events()

                # Should emit lineage for model and seed, but not test or exposure
                assert mock_emit_lineage.call_count == 2

                # Get all downstream resources that were emitted
                downstream_resources = [
                    call.kwargs["downstream_resources"][0]["prefect.resource.id"]
                    for call in mock_emit_lineage.call_args_list
                ]

                # Verify correct resources were emitted
                assert "postgres://schema/model_table" in downstream_resources
                assert "postgres://schema/seed_table" in downstream_resources
                assert "postgres://schema/test_table" not in downstream_resources
                assert "postgres://schema/exposure_table" not in downstream_resources

                # Verify the structure of one of the lineage calls
                model_call = next(
                    call
                    for call in mock_emit_lineage.call_args_list
                    if call.kwargs["downstream_resources"][0]["prefect.resource.id"]
                    == "postgres://schema/model_table"
                )
                assert model_call.kwargs["downstream_resources"][0] == {
                    "prefect.resource.id": "postgres://schema/model_table",
                    "prefect.resource.lineage-group": "global",
                    "prefect.resource.role": NodeType.Model,
                    "prefect.resource.name": "model",
                }

        test_flow()

        # Verify parse was called only when manifest wasn't provided
        assert mock_dbt_runner.invoke.called == (not provide_manifest)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("provide_manifest", [True, False])
    async def test_aemit_lineage_events(
        self, mock_dbt_runner, settings, mock_manifest_with_nodes, provide_manifest
    ):
        """Test that lineage events are emitted correctly for all relevant nodes (async version)."""
        runner = PrefectDbtRunner(
            settings=settings,
            manifest=mock_manifest_with_nodes if provide_manifest else None,
        )

        if not provide_manifest:
            # Setup the mock to return our manifest when parse() is called
            mock_dbt_runner.invoke.return_value.result = mock_manifest_with_nodes

        @flow(flow_run_name="test-flow-name")
        async def test_flow():
            with patch(
                "prefect_dbt.core.runner.emit_external_resource_lineage"
            ) as mock_emit_lineage:
                await runner.aemit_lineage_events()

                # Should emit lineage for model and seed, but not test or exposure
                assert mock_emit_lineage.call_count == 2

                # Get all downstream resources that were emitted
                downstream_resources = [
                    call.kwargs["downstream_resources"][0]["prefect.resource.id"]
                    for call in mock_emit_lineage.call_args_list
                ]

                # Verify correct resources were emitted
                assert "postgres://schema/model_table" in downstream_resources
                assert "postgres://schema/seed_table" in downstream_resources
                assert "postgres://schema/test_table" not in downstream_resources
                assert "postgres://schema/exposure_table" not in downstream_resources

                # Verify the structure of one of the lineage calls
                model_call = next(
                    call
                    for call in mock_emit_lineage.call_args_list
                    if call.kwargs["downstream_resources"][0]["prefect.resource.id"]
                    == "postgres://schema/model_table"
                )
                assert model_call.kwargs["downstream_resources"][0] == {
                    "prefect.resource.id": "postgres://schema/model_table",
                    "prefect.resource.lineage-group": "global",
                    "prefect.resource.role": NodeType.Model,
                    "prefect.resource.name": "model",
                }

        await test_flow()

        # Verify parse was called only when manifest wasn't provided
        assert mock_dbt_runner.invoke.called == (not provide_manifest)
