import os
import signal
import subprocess
import sys
from typing import Any, Literal
from unittest.mock import MagicMock, patch

import pytest
import uv

from prefect import flow
from prefect._experimental.bundles import (
    _discover_local_dependencies,
    _extract_imports_from_source,
    _is_local_module,
    _pickle_local_modules_by_value,
    convert_step_to_command,
    create_bundle_for_flow_run,
    execute_bundle_in_subprocess,
)
from prefect.client.orchestration import PrefectClient
from prefect.context import TagsContext
from prefect.exceptions import Abort


@pytest.mark.parametrize("engine_type", ["sync", "async"])
class TestExecuteBundleInSubprocess:
    @pytest.fixture(autouse=True)
    def mock_subprocess_check_call(self, monkeypatch: pytest.MonkeyPatch):
        mock_subprocess_check_call = MagicMock()
        monkeypatch.setattr(subprocess, "check_call", mock_subprocess_check_call)
        return mock_subprocess_check_call

    @pytest.fixture(autouse=True)
    def mock_subprocess_check_output(self, monkeypatch: pytest.MonkeyPatch):
        mock_subprocess_check_output = MagicMock(
            return_value=b"the-whole-enchilada==0.5.3"
        )
        monkeypatch.setattr(subprocess, "check_output", mock_subprocess_check_output)
        return mock_subprocess_check_output

    async def test_basic(
        self,
        prefect_client: PrefectClient,
        engine_type: Literal["sync", "async"],
        mock_subprocess_check_call: MagicMock,
    ):
        if engine_type == "sync":

            @flow(
                name="TestExecuteBundleInSubprocess.test_basic[sync]",
                persist_result=True,
            )
            def simple_flow():
                return "I'm a simple flow, and as a simple flow I believe in speaking plainly."
        else:

            @flow(
                name="TestExecuteBundleInSubprocess.test_basic[async]",
                persist_result=True,
            )
            async def simple_flow():
                return "I'm a simple flow, and as a simple flow I believe in speaking plainly."

        flow_run = await prefect_client.create_flow_run(
            flow=simple_flow,
        )

        bundle = create_bundle_for_flow_run(simple_flow, flow_run)

        assert bundle["dependencies"] == "the-whole-enchilada==0.5.3"

        process = execute_bundle_in_subprocess(bundle)

        process.join()
        assert process.exitcode == 0

        mock_subprocess_check_call.assert_called_once_with(
            [
                uv.find_uv_bin(),
                "pip",
                "install",
                "the-whole-enchilada==0.5.3",
            ],
            env=os.environ,
        )

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state is not None
        assert flow_run.state.is_completed()
        assert (
            await flow_run.state.result()
            == "I'm a simple flow, and as a simple flow I believe in speaking plainly."
        )

    async def test_flow_ends_in_failed(
        self, prefect_client: PrefectClient, engine_type: Literal["sync", "async"]
    ):
        if engine_type == "sync":

            @flow(name="TestExecuteBundleInSubprocess.test_flow_ends_in_failed[sync]")
            def foo():
                raise ValueError("xyz")
        else:

            @flow(name="TestExecuteBundleInSubprocess.test_flow_ends_in_failed[async]")
            async def foo():
                raise ValueError("xyz")

        flow_run = await prefect_client.create_flow_run(flow=foo)

        bundle = create_bundle_for_flow_run(foo, flow_run)
        process = execute_bundle_in_subprocess(bundle)

        process.join()
        assert process.exitcode == 1

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state is not None
        assert flow_run.state.is_failed()

    async def test_with_parameters(
        self, prefect_client: PrefectClient, engine_type: Literal["sync", "async"]
    ):
        if engine_type == "sync":

            @flow(
                name="TestExecuteBundleInSubprocess.test_with_parameters[sync]",
                persist_result=True,
            )
            def flow_with_parameters(x: int, y: str):
                return f"x: {x}, y: {y}"
        else:

            @flow(
                name="TestExecuteBundleInSubprocess.test_with_parameters[async]",
                persist_result=True,
            )
            async def flow_with_parameters(x: int, y: str):
                return f"x: {x}, y: {y}"

        flow_run = await prefect_client.create_flow_run(
            flow=flow_with_parameters,
            parameters={"x": 42, "y": "hello"},
        )

        bundle = create_bundle_for_flow_run(flow_with_parameters, flow_run)
        process = execute_bundle_in_subprocess(bundle)

        process.join()
        assert process.exitcode == 0

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state is not None
        assert flow_run.state.is_completed()
        assert await flow_run.state.result() == "x: 42, y: hello"

    async def test_with_provided_context(
        self, prefect_client: PrefectClient, engine_type: Literal["sync", "async"]
    ):
        if engine_type == "sync":

            @flow(
                name="TestExecuteBundleInSubprocess.test_with_provided_context[sync]",
                persist_result=True,
            )
            def context_flow():
                return TagsContext.get().current_tags
        else:

            @flow(
                name="TestExecuteBundleInSubprocess.test_with_provided_context[async]",
                persist_result=True,
            )
            async def context_flow():
                return TagsContext.get().current_tags

        context = {"tags_context": TagsContext(current_tags={"foo", "bar"}).serialize()}

        flow_run = await prefect_client.create_flow_run(
            flow=context_flow,
        )

        bundle = create_bundle_for_flow_run(
            flow=context_flow, flow_run=flow_run, context=context
        )
        process = execute_bundle_in_subprocess(bundle)
        process.join()
        assert process.exitcode == 0

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state is not None
        assert flow_run.state.is_completed()
        assert await flow_run.state.result() == {"foo", "bar"}

    async def test_flow_is_aborted(
        self, engine_type: Literal["sync", "async"], prefect_client: PrefectClient
    ):
        if engine_type == "sync":

            @flow(
                name="TestExecuteBundleInSubprocess.test_flow_is_aborted[sync]",
                persist_result=True,
            )
            def foo():
                raise Abort()
        else:

            @flow(
                name="TestExecuteBundleInSubprocess.test_flow_is_aborted[async]",
                persist_result=True,
            )
            async def foo():
                raise Abort()

        flow_run = await prefect_client.create_flow_run(flow=foo)

        bundle = create_bundle_for_flow_run(foo, flow_run)
        process = execute_bundle_in_subprocess(bundle)
        process.join()
        assert process.exitcode == 0

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        # Stays in running state because the flow run is aborted manually
        assert flow_run.state is not None
        assert flow_run.state.is_running()

    async def test_flow_raises_a_base_exception(
        self, prefect_client: PrefectClient, engine_type: Literal["sync", "async"]
    ):
        if engine_type == "sync":

            @flow(
                name="TestExecuteBundleInSubprocess.test_flow_raises_a_base_exception[sync]",
                persist_result=True,
            )
            def foo():
                raise BaseException()
        else:

            @flow(
                name="TestExecuteBundleInSubprocess.test_flow_raises_a_base_exception[async]",
                persist_result=True,
            )
            async def foo():
                raise BaseException()

        flow_run = await prefect_client.create_flow_run(flow=foo)

        bundle = create_bundle_for_flow_run(foo, flow_run)
        process = execute_bundle_in_subprocess(bundle)
        process.join()
        assert process.exitcode == 1

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state is not None
        assert flow_run.state.is_crashed()

    async def test_flow_process_is_killed(
        self, prefect_client: PrefectClient, engine_type: Literal["sync", "async"]
    ):
        if engine_type == "sync":

            @flow(
                name="TestExecuteBundleInSubprocess.test_flow_process_is_killed[sync]",
                persist_result=True,
            )
            def foo():
                signal.raise_signal(signal.SIGKILL)
        else:

            @flow(
                name="TestExecuteBundleInSubprocess.test_flow_process_is_killed[async]",
                persist_result=True,
            )
            async def foo():
                signal.raise_signal(signal.SIGKILL)

        flow_run = await prefect_client.create_flow_run(flow=foo)

        bundle = create_bundle_for_flow_run(foo, flow_run)
        process = execute_bundle_in_subprocess(bundle)
        process.join()
        assert process.exitcode == -9

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        # Stays in running state because the process died
        assert flow_run.state is not None
        assert flow_run.state.is_running()

    async def test_filters_local_file_dependencies(
        self,
        prefect_client: PrefectClient,
        engine_type: Literal["sync", "async"],
        monkeypatch: pytest.MonkeyPatch,
    ):
        mock_dependencies_output = b"package1==1.0.0\nfile:///path/to/local/package\npackage2==2.0.0\n-e file:///path/to/another/local\npackage3==3.0.0"
        mock_subprocess_check_output = MagicMock(return_value=mock_dependencies_output)
        monkeypatch.setattr(subprocess, "check_output", mock_subprocess_check_output)

        if engine_type == "sync":

            @flow(
                name="TestExecuteBundleInSubprocess.test_filters_local_file_dependencies[sync]"
            )
            def simple_flow():
                return "test"
        else:

            @flow(
                name="TestExecuteBundleInSubprocess.test_filters_local_file_dependencies[async]"
            )
            async def simple_flow():
                return "test"

        flow_run = await prefect_client.create_flow_run(flow=simple_flow)
        bundle = create_bundle_for_flow_run(simple_flow, flow_run)

        # Verify that local file dependencies are filtered out
        assert (
            bundle["dependencies"]
            == "package1==1.0.0\npackage2==2.0.0\npackage3==3.0.0"
        )


class TestConvertStepToCommand:
    def test_basic(self):
        step = {
            "prefect_aws.experimental.bundles.upload": {
                "requires": "prefect-aws==0.5.5",
                "bucket": "test-bucket",
                "aws_credentials_block_name": "my-creds",
            }
        }

        python_version_info = sys.version_info
        command = convert_step_to_command(step, "test-key")
        assert command == [
            "uv",
            "run",
            "--with",
            "prefect-aws==0.5.5",
            "--python",
            f"{python_version_info.major}.{python_version_info.minor}",
            "-m",
            "prefect_aws.experimental.bundles.upload",
            "--bucket",
            "test-bucket",
            "--aws-credentials-block-name",
            "my-creds",
            "--key",
            "test-key",
        ]

    def test_with_no_requires(self):
        step = {
            "prefect_mock.experimental.bundles.upload": {
                "bucket": "test-bucket",
            }
        }

        python_version_info = sys.version_info
        command = convert_step_to_command(step, "test-key")
        assert command == [
            "uv",
            "run",
            "--python",
            f"{python_version_info.major}.{python_version_info.minor}",
            "-m",
            "prefect_mock.experimental.bundles.upload",
            "--bucket",
            "test-bucket",
            "--key",
            "test-key",
        ]

    def test_raises_if_multiple_functions_are_provided(self):
        step: dict[str, Any] = {
            "prefect_mock.experimental.bundles.upload": {},
            "prefect_mock.experimental.bundles.download": {},
        }
        with pytest.raises(ValueError, match="Expected exactly one function in step"):
            convert_step_to_command(step, "test-key")

    def test_raises_if_no_function_is_provided(self):
        step: dict[str, Any] = {}
        with pytest.raises(ValueError, match="Expected exactly one function in step"):
            convert_step_to_command(step, "test-key")


class TestLocalDependencyDiscovery:
    def test_is_local_module_builtin(self):
        """Test that built-in modules are not considered local."""
        assert not _is_local_module("sys")
        assert not _is_local_module("os")
        assert not _is_local_module("json")

    @pytest.mark.skipif(
        not hasattr(sys, "stdlib_module_names"), reason="Requires Python 3.10+"
    )
    def test_is_local_module_stdlib(self):
        """Test that standard library modules are not considered local."""
        assert not _is_local_module("logging")
        assert not _is_local_module("asyncio")
        assert not _is_local_module("unittest")

    def test_is_local_module_site_packages(self):
        """Test that modules in site-packages are not considered local."""
        # pytest is definitely installed in site-packages
        assert not _is_local_module("pytest")

    def test_extract_imports_from_source(self):
        """Test extraction of import statements from source code."""
        source = """
import os
import sys
from pathlib import Path
from typing import List, Dict
import numpy as np
from my_module import helper
from my_package.submodule import function
"""
        imports = _extract_imports_from_source(source)

        assert "os" in imports
        assert "sys" in imports
        assert "pathlib" in imports
        assert "typing" in imports
        assert "numpy" in imports
        assert "my_module" in imports
        assert "my_package.submodule" in imports
        # These should not be included as they are individual items, not modules
        assert "my_module.helper" not in imports
        assert "my_package.submodule.function" not in imports

    def test_extract_imports_handles_syntax_errors(self):
        """Test that import extraction handles syntax errors gracefully."""
        source = "this is not valid python syntax !!!"
        imports = _extract_imports_from_source(source)
        assert imports == set()

    def test_discover_local_dependencies_with_no_module(self):
        """Test discovery when flow has no module (e.g., defined in REPL)."""

        @flow
        def repl_flow():
            return "repl"

        # Mock the flow to have no module
        with patch("inspect.getmodule", return_value=None):
            deps = _discover_local_dependencies(repl_flow)
            assert deps == set()

    def test_pickle_local_modules_context_manager(self):
        """Test the context manager for registering local modules."""

        @flow
        def test_flow():
            return "test"

        # Track which modules were registered/unregistered
        registered = []
        unregistered = []

        def mock_register(module):
            registered.append(module)

        def mock_unregister(module):
            unregistered.append(module)

        with patch("cloudpickle.register_pickle_by_value", side_effect=mock_register):
            with patch(
                "cloudpickle.unregister_pickle_by_value", side_effect=mock_unregister
            ):
                with patch(
                    "prefect._experimental.bundles._discover_local_dependencies",
                    return_value={"test_module"},
                ):
                    with patch("importlib.import_module") as mock_import:
                        mock_module = MagicMock()
                        mock_module.__name__ = "test_module"
                        mock_import.return_value = mock_module

                        with _pickle_local_modules_by_value(test_flow):
                            # Inside context, module should be registered
                            assert len(registered) == 1
                            assert registered[0] == mock_module

                        # After context, module should be unregistered
                        assert len(unregistered) == 1
                        assert unregistered[0] == mock_module

    def test_pickle_local_modules_handles_import_errors(self, caplog):
        """Test that import errors are handled gracefully."""

        @flow
        def test_flow():
            return "test"

        with patch(
            "prefect._experimental.bundles._discover_local_dependencies",
            return_value={"nonexistent_module"},
        ):
            with _pickle_local_modules_by_value(test_flow):
                pass

            # Check that a debug message was logged about the failure
            assert "Failed to register module nonexistent_module" in caplog.text
