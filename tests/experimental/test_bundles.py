import os
import signal
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Literal
from unittest.mock import MagicMock, patch

import pytest
import uv

import prefect._experimental.bundles as bundles_module
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


def test_launcher_type_is_exported_from_bundles_module() -> None:
    import prefect.flows as flows
    from prefect._experimental.bundles import BundleLauncher, BundleLauncherOverride

    launcher: BundleLauncher = ["python"]
    override: BundleLauncherOverride = {"execution": ["python"]}

    assert launcher == ["python"]
    assert override == {"execution": ["python"]}
    assert not hasattr(flows, "BundleLauncher")


@pytest.mark.usefixtures("use_hosted_api_server")
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

        result = create_bundle_for_flow_run(simple_flow, flow_run)
        bundle = result["bundle"]

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

        result = create_bundle_for_flow_run(foo, flow_run)
        bundle = result["bundle"]
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

        result = create_bundle_for_flow_run(flow_with_parameters, flow_run)
        bundle = result["bundle"]
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

        result = create_bundle_for_flow_run(
            flow=context_flow, flow_run=flow_run, context=context
        )
        bundle = result["bundle"]
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

        result = create_bundle_for_flow_run(foo, flow_run)
        bundle = result["bundle"]
        process = execute_bundle_in_subprocess(bundle)
        process.join()
        assert process.exitcode == 0

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        # Stays in running state because the flow run is aborted manually
        assert flow_run.state is not None
        assert flow_run.state.is_running()

    def test_extract_and_run_flow_configures_listener_before_bundle_deserialization(
        self,
        engine_type: Literal["sync", "async"],
        monkeypatch: pytest.MonkeyPatch,
    ):
        calls: list[str] = []

        monkeypatch.setattr(
            bundles_module, "configure_from_env", lambda: calls.append("configure")
        )
        monkeypatch.setattr(
            bundles_module,
            "_deserialize_bundle_object",
            lambda value: calls.append(f"deserialize:{value}") or MagicMock(),
        )
        monkeypatch.setattr(
            bundles_module.FlowRun,
            "model_validate",
            lambda value: MagicMock(id="flow-run-id"),
        )
        monkeypatch.setattr(
            bundles_module,
            "get_settings_context",
            lambda: MagicMock(profile="test-profile"),
        )
        monkeypatch.setattr(
            bundles_module,
            "SettingsContext",
            lambda **kwargs: nullcontext(),
        )
        monkeypatch.setattr(
            bundles_module,
            "handle_engine_signals",
            lambda flow_run_id: nullcontext(),
        )
        monkeypatch.setattr(bundles_module, "run_flow", lambda **kwargs: None)

        bundles_module._extract_and_run_flow(
            bundle={
                "function": "function-payload",
                "context": "context-payload",
                "flow_run": {},
                "dependencies": "",
            }
        )

        assert calls == [
            "configure",
            "deserialize:function-payload",
            "deserialize:context-payload",
        ]

    def test_execute_bundle_in_subprocess_drops_none_env_values(
        self,
        engine_type: Literal["sync", "async"],
        monkeypatch: pytest.MonkeyPatch,
    ):
        captured: dict[str, Any] = {}

        class _FakeProcess:
            def __init__(self, *, target: Any, kwargs: dict[str, Any]) -> None:
                captured["target"] = target
                captured["kwargs"] = kwargs

            def start(self) -> None:
                captured["started"] = True

        class _FakeContext:
            def Process(self, target: Any, kwargs: dict[str, Any]) -> _FakeProcess:
                return _FakeProcess(target=target, kwargs=kwargs)

        monkeypatch.setattr(
            bundles_module.multiprocessing,
            "get_context",
            lambda method: _FakeContext(),
        )
        monkeypatch.setattr(
            bundles_module,
            "get_current_settings",
            lambda: MagicMock(to_environment_variables=MagicMock(return_value={})),
        )
        monkeypatch.setattr(bundles_module.os, "environ", {"INHERITED": "present"})

        process = execute_bundle_in_subprocess(
            {
                "function": "function-payload",
                "context": "context-payload",
                "flow_run": {},
                "dependencies": "",
            },
            env={"KEEP_ME": "value", "DROP_ME": None},
        )

        assert isinstance(process, _FakeProcess)
        assert captured["started"] is True
        assert captured["target"] is bundles_module._extract_and_run_flow
        assert captured["kwargs"]["env"] == {
            "INHERITED": "present",
            "KEEP_ME": "value",
        }

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

        result = create_bundle_for_flow_run(foo, flow_run)
        bundle = result["bundle"]
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

        result = create_bundle_for_flow_run(foo, flow_run)
        bundle = result["bundle"]
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
        result = create_bundle_for_flow_run(simple_flow, flow_run)
        bundle = result["bundle"]

        # Verify that local file dependencies are filtered out
        assert (
            bundle["dependencies"]
            == "package1==1.0.0\npackage2==2.0.0\npackage3==3.0.0"
        )


class TestConvertStepToCommand:
    @pytest.fixture(autouse=True)
    def pin_publishable_prefect_version(self, monkeypatch: pytest.MonkeyPatch) -> str:
        """
        Pin `prefect.__version__` to a publishable (non-local) version so
        tests are deterministic regardless of how Prefect is installed in
        the test environment. In CI, editable installs from the checkout
        can produce local version identifiers (e.g. `3.6.28+4.gabc1234`)
        that would otherwise cause the pin logic to skip.
        """
        publishable_version = "3.6.99"
        monkeypatch.setattr(bundles_module.prefect, "__version__", publishable_version)
        return publishable_version

    def test_basic(self, pin_publishable_prefect_version: str):
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
            f"prefect-aws==0.5.5,prefect=={pin_publishable_prefect_version}",
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

    def test_appends_prefect_pin_when_missing(
        self, pin_publishable_prefect_version: str
    ):
        """Bundle steps with requires but no Prefect pin get one appended."""
        step = {
            "prefect_aws.experimental.bundles.execute": {
                "requires": ["prefect-aws"],
                "bucket": "test-bucket",
            }
        }

        python_version_info = sys.version_info
        command = convert_step_to_command(step, "test-key")
        assert command == [
            "uv",
            "run",
            "--with",
            f"prefect-aws,prefect=={pin_publishable_prefect_version}",
            "--python",
            f"{python_version_info.major}.{python_version_info.minor}",
            "-m",
            "prefect_aws.experimental.bundles.execute",
            "--bucket",
            "test-bucket",
            "--key",
            "test-key",
        ]

    def test_rewrites_bare_prefect_requirement(
        self, pin_publishable_prefect_version: str
    ):
        """A bare `prefect` requirement is rewritten to the exact current version."""
        step = {
            "prefect_aws.experimental.bundles.execute": {
                "requires": ["prefect", "prefect-aws==0.5.5"],
                "bucket": "test-bucket",
            }
        }

        python_version_info = sys.version_info
        command = convert_step_to_command(step, "test-key")
        assert command == [
            "uv",
            "run",
            "--with",
            f"prefect=={pin_publishable_prefect_version},prefect-aws==0.5.5",
            "--python",
            f"{python_version_info.major}.{python_version_info.minor}",
            "-m",
            "prefect_aws.experimental.bundles.execute",
            "--bucket",
            "test-bucket",
            "--key",
            "test-key",
        ]

    def test_rewrites_ranged_prefect_requirement(
        self, pin_publishable_prefect_version: str
    ):
        """`prefect>=X` from integration requires is rewritten to the exact version."""
        step = {
            "prefect_aws.experimental.bundles.execute": {
                "requires": ["prefect-aws", "prefect>=3.6.24"],
                "bucket": "test-bucket",
            }
        }

        command = convert_step_to_command(step, "test-key")
        assert "--with" in command
        with_value = command[command.index("--with") + 1]
        assert f"prefect=={pin_publishable_prefect_version}" in with_value.split(",")
        # The original `prefect>=3.6.24` requirement should have been replaced,
        # not left alongside the pin.
        assert "prefect>=3.6.24" not in with_value.split(",")

    def test_rewrites_prefect_with_extras_and_markers(
        self, pin_publishable_prefect_version: str
    ):
        """Extras and markers are preserved when rewriting a Prefect requirement."""
        step = {
            "prefect_aws.experimental.bundles.execute": {
                "requires": [
                    'prefect[aws]>=3.0 ; python_version >= "3.10"',
                    "prefect-aws",
                ],
                "bucket": "test-bucket",
            }
        }

        command = convert_step_to_command(step, "test-key")
        with_value = command[command.index("--with") + 1]
        parts = with_value.split(",")
        assert any(
            part.startswith(f"prefect[aws]=={pin_publishable_prefect_version}")
            for part in parts
        ), parts
        assert any('python_version >= "3.10"' in part for part in parts), parts

    def test_skips_pin_for_local_versions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pinning is skipped entirely for local/unpublishable Prefect versions."""
        monkeypatch.setattr(bundles_module.prefect, "__version__", "3.6.24+dev.abc1234")

        step = {
            "prefect_aws.experimental.bundles.execute": {
                "requires": ["prefect-aws"],
                "bucket": "test-bucket",
            }
        }

        python_version_info = sys.version_info
        command = convert_step_to_command(step, "test-key")
        assert command == [
            "uv",
            "run",
            "--with",
            "prefect-aws",
            "--python",
            f"{python_version_info.major}.{python_version_info.minor}",
            "-m",
            "prefect_aws.experimental.bundles.execute",
            "--bucket",
            "test-bucket",
            "--key",
            "test-key",
        ]

    def test_skips_pin_for_non_bundle_modules(self) -> None:
        """Only bundle upload/execute modules get the Prefect pin."""
        step = {
            "some_other_module.do_stuff": {
                "requires": ["prefect-aws"],
                "bucket": "test-bucket",
            }
        }

        python_version_info = sys.version_info
        command = convert_step_to_command(step, "test-key")
        assert command == [
            "uv",
            "run",
            "--with",
            "prefect-aws",
            "--python",
            f"{python_version_info.major}.{python_version_info.minor}",
            "-m",
            "some_other_module.do_stuff",
            "--bucket",
            "test-bucket",
            "--key",
            "test-key",
        ]

    def test_launcher_behavior_is_preserved(self):
        """Launcher steps are not modified by the Prefect pin logic."""
        step = {
            "prefect_aws.experimental.bundles.execute": {
                "launcher": ["python"],
                "bucket": "test-bucket",
            }
        }

        command = convert_step_to_command(step, "test-key")
        assert command == [
            "python",
            "-m",
            "prefect_aws.experimental.bundles.execute",
            "--bucket",
            "test-bucket",
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

    def test_with_launcher(self):
        step = {
            "prefect_mock.experimental.bundles.execute": {
                "bucket": "test-bucket",
                "launcher": ["python"],
            }
        }

        command = convert_step_to_command(step, "test-key")
        assert command == [
            "python",
            "-m",
            "prefect_mock.experimental.bundles.execute",
            "--bucket",
            "test-bucket",
            "--key",
            "test-key",
        ]

    def test_with_multi_part_launcher(self):
        step = {
            "prefect_mock.experimental.bundles.execute": {
                "bucket": "test-bucket",
                "launcher": ["poetry", "run", "python"],
            }
        }

        command = convert_step_to_command(step, "test-key")
        assert command == [
            "poetry",
            "run",
            "python",
            "-m",
            "prefect_mock.experimental.bundles.execute",
            "--bucket",
            "test-bucket",
            "--key",
            "test-key",
        ]

    def test_raises_if_launcher_is_empty(self):
        step = {
            "prefect_mock.experimental.bundles.execute": {
                "launcher": [],
            }
        }

        with pytest.raises(ValueError, match="launcher must be a non-empty list"):
            convert_step_to_command(step, "test-key")

    def test_raises_if_launcher_item_is_invalid(self):
        step = {
            "prefect_mock.experimental.bundles.execute": {
                "launcher": ["python", ""],
            }
        }

        with pytest.raises(
            ValueError, match=r"launcher\[1\] must be a non-empty string"
        ):
            convert_step_to_command(step, "test-key")

    def test_raises_if_launcher_and_requires_are_provided(self):
        step = {
            "prefect_mock.experimental.bundles.execute": {
                "requires": "prefect-mock",
                "launcher": ["python"],
            }
        }

        with pytest.raises(
            ValueError, match="launcher cannot be combined with step requirements"
        ):
            convert_step_to_command(step, "test-key")

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

    def test_pickle_local_modules_handles_import_errors(
        self, caplog: pytest.LogCaptureFixture
    ):
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

    def test_discover_deeply_nested_local_dependencies(self, tmp_path: Path):
        """Test that local dependencies are discovered recursively through multiple levels.

        This tests the scenario where:
        - flow_module imports module_b
        - module_b imports module_c
        - module_c imports module_d

        All modules should be discovered, including module_d which is 3 levels deep.
        """
        # Create temporary package structure with deep nesting
        package_root = tmp_path / "test_packages"
        package_root.mkdir()

        # Create flow_module package
        flow_pkg = package_root / "flow_module"
        flow_pkg.mkdir()
        (flow_pkg / "__init__.py").write_text("")

        # Create module_b package
        module_b_pkg = package_root / "module_b"
        module_b_pkg.mkdir()
        (module_b_pkg / "__init__.py").write_text("")

        # Create module_c package
        module_c_pkg = package_root / "module_c"
        module_c_pkg.mkdir()
        (module_c_pkg / "__init__.py").write_text("")

        # Create module_d package (deepest level)
        module_d_pkg = package_root / "module_d"
        module_d_pkg.mkdir()
        (module_d_pkg / "__init__.py").write_text("")

        # Create module_d with a simple function
        (module_d_pkg / "utils.py").write_text("""
def function_d():
    return "d"
""")

        # Create module_c that imports from module_d
        (module_c_pkg / "utils.py").write_text("""
from module_d.utils import function_d

def function_c():
    return function_d()
""")

        # Create module_b that imports from module_c
        (module_b_pkg / "utils.py").write_text("""
from module_c.utils import function_c

def function_b():
    return function_c()
""")

        # Create flow_module that imports from module_b
        (flow_pkg / "my_flow.py").write_text("""
from module_b.utils import function_b
from prefect import flow

@flow
def test_flow():
    return function_b()
""")

        # Add package_root to sys.path so modules can be imported
        sys.path.insert(0, str(package_root))

        try:
            # Import the flow module and get the flow
            import flow_module.my_flow

            flow_obj = flow_module.my_flow.test_flow

            # Discover dependencies
            deps = _discover_local_dependencies(flow_obj)

            # All four modules should be discovered
            assert "flow_module.my_flow" in deps, (
                "Flow module itself should be discovered"
            )
            assert "module_b.utils" in deps, "First-level import should be discovered"
            assert "module_c.utils" in deps, "Second-level import should be discovered"
            assert "module_d.utils" in deps, "Third-level import should be discovered"

        finally:
            # Clean up sys.path and sys.modules
            sys.path.remove(str(package_root))
            for module in list(sys.modules.keys()):
                if module.startswith(
                    ("flow_module", "module_b", "module_c", "module_d")
                ):
                    del sys.modules[module]
