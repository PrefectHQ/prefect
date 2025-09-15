import os
import shutil
import subprocess
import sys
import warnings
from pathlib import Path
from textwrap import dedent
from typing import Optional
from unittest.mock import ANY, call

import pytest
import uv

from prefect._internal.compatibility.deprecated import PrefectDeprecationWarning
from prefect.blocks.core import Block
from prefect.blocks.system import Secret
from prefect.client.orchestration import PrefectClient
from prefect.deployments.steps import run_step
from prefect.deployments.steps.core import StepExecutionError, run_steps
from prefect.deployments.steps.pull import agit_clone, set_working_directory
from prefect.deployments.steps.utility import run_shell_script
from prefect.testing.utilities import AsyncMock, MagicMock
from prefect.utilities.filesystem import tmpchdir


@pytest.fixture
async def variables(prefect_client: PrefectClient):
    await prefect_client._client.post(
        "/variables/", json={"name": "test_variable_1", "value": "test_value_1"}
    )
    await prefect_client._client.post(
        "/variables/", json={"name": "test_variable_2", "value": "test_value_2"}
    )


@pytest.fixture(scope="session")
def set_dummy_env_var():
    import os

    os.environ["DUMMY_ENV_VAR"] = "dummy"


class TestRunStep:
    async def test_run_step_runs_importable_functions(self):
        output = await run_step(
            {
                "prefect.deployments.steps.run_shell_script": {
                    "script": "echo 'this is a test'",
                }
            },
        )
        assert isinstance(output, dict)
        assert output == {
            "stdout": "this is a test",
            "stderr": "",
        }

    async def test_run_step_errors_with_improper_format(self):
        with pytest.raises(ValueError, match="unexpected"):
            await run_step(
                {
                    "prefect.deployments.steps.run_shell_script": {
                        "script": "echo 'this is a test'"
                    },
                    "jedi": 0,
                }
            )

    async def test_run_step_resolves_block_document_references_before_running(self):
        await Secret(value="echo 'I am a secret!'").save(name="test-secret")

        output = await run_step(
            {
                "prefect.deployments.steps.run_shell_script": {
                    "script": "{{ prefect.blocks.secret.test-secret }}",
                }
            }
        )
        assert isinstance(output, dict)
        assert output == {
            "stdout": "I am a secret!",
            "stderr": "",
        }

    async def test_run_step_resolves_environment_variables_before_running(
        self, monkeypatch
    ):
        monkeypatch.setenv("TEST_ENV_VAR", "test_value")
        output = await run_step(
            {
                "prefect.deployments.steps.run_shell_script": {
                    "script": 'echo "{{ $TEST_ENV_VAR }}"',
                }
            }
        )
        assert isinstance(output, dict)
        assert output == {
            "stdout": "test_value",
            "stderr": "",
        }

    async def test_run_step_resolves_variables_before_running(self, variables):
        output = await run_step(
            {
                "prefect.deployments.steps.run_shell_script": {
                    "script": (
                        "echo '{{ prefect.variables.test_variable_1 }}:{{"
                        " prefect.variables.test_variable_2 }}'"
                    ),
                }
            }
        )
        assert isinstance(output, dict)
        assert output == {
            "stdout": "test_value_1:test_value_2",
            "stderr": "",
        }

    async def test_run_step_runs_async_functions(self):
        output = await run_step(
            {
                "anyio.run_process": {
                    "command": ["echo", "hello world"],
                }
            }
        )
        assert output.returncode == 0
        assert output.stdout.decode().strip() == "hello world"

    async def test_requirement_installation_successful(self, monkeypatch):
        """
        Test that the function attempts to install the package and succeeds.
        """
        import_module_mock = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.core.import_module", import_module_mock
        )

        monkeypatch.setattr(subprocess, "check_call", MagicMock())

        import_object_mock = MagicMock(side_effect=[ImportError, lambda x: x])
        monkeypatch.setattr(
            "prefect.deployments.steps.core.import_object", import_object_mock
        )

        await run_step(
            {"test_module.test_function": {"requires": "test-package>=1.0.0", "x": 1}}
        )

        import_module_mock.assert_called_once_with("test_package")
        assert (
            import_object_mock.call_count == 2
        )  # once before and once after installation
        subprocess.check_call.assert_called_once_with(
            [uv.find_uv_bin(), "pip", "install", "test-package>=1.0.0"],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

    @pytest.mark.parametrize(
        "package,expected",
        [
            ("prefect-aws", "prefect[aws]"),
            ("prefect-gcp", "prefect[gcp]"),
            ("prefect-azure", "prefect[azure]"),
            ("prefect-docker", "prefect[docker]"),
            ("prefect-kubernetes", "prefect[kubernetes]"),
        ],
    )
    async def test_requirement_installation_uses_prefect_extras(
        self, monkeypatch, package, expected
    ):
        import_module_mock = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.core.import_module", import_module_mock
        )

        monkeypatch.setattr(subprocess, "check_call", MagicMock())

        import_object_mock = MagicMock(side_effect=[ImportError, lambda x: x])
        monkeypatch.setattr(
            "prefect.deployments.steps.core.import_object", import_object_mock
        )

        await run_step({"test_module.test_function": {"requires": package, "x": 1}})

        import_module_mock.assert_called_once_with(package.replace("-", "_"))
        assert (
            import_object_mock.call_count == 2
        )  # once before and once after installation
        subprocess.check_call.assert_called_once_with(
            [uv.find_uv_bin(), "pip", "install", expected],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

    async def test_install_multiple_requirements(self, monkeypatch):
        """
        Test that passing multiple requirements installs all of them.
        """
        import_module_mock = MagicMock(side_effect=[None, ImportError])
        monkeypatch.setattr(
            "prefect.deployments.steps.core.import_module", import_module_mock
        )

        monkeypatch.setattr(subprocess, "check_call", MagicMock())

        import_object_mock = MagicMock(side_effect=[lambda x: x])
        monkeypatch.setattr(
            "prefect.deployments.steps.core.import_object", import_object_mock
        )

        await run_step(
            {
                "test_module.test_function": {
                    "requires": ["test-package>=1.0.0", "another"],
                    "x": 1,
                }
            }
        )

        import_module_mock.assert_has_calls([call("test_package"), call("another")])
        subprocess.check_call.assert_called_once_with(
            [uv.find_uv_bin(), "pip", "install", "test-package>=1.0.0", "another"],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

    async def test_requirement_installation_failure(self, monkeypatch, caplog):
        """
        Test that the function logs a warning if it fails to install the package.
        """
        # Mocking the import_module function to always raise ImportError
        monkeypatch.setattr(
            "prefect.deployments.steps.core.import_module",
            MagicMock(side_effect=ImportError),
        )

        # Mock subprocess.check_call to simulate failed package installation
        monkeypatch.setattr(
            subprocess,
            "check_call",
            MagicMock(side_effect=subprocess.CalledProcessError(1, ["pip"])),
        )

        with pytest.raises(ImportError):
            await run_step(
                {
                    "test_module.test_function": {
                        "requires": "nonexistent-package>=1.0.0"
                    }
                }
            )

        assert subprocess.check_call.called
        record = next(
            (
                record
                for record in caplog.records
                if "Unable to install required packages" in record.message
            ),
            None,
        )
        assert record is not None, "No warning was logged"
        assert record.levelname == "WARNING"


class TestRunSteps:
    async def test_run_steps_runs_multiple_steps(self):
        steps = [
            {
                "prefect.deployments.steps.run_shell_script": {
                    "script": "echo 'this is a test'",
                    "id": "why_not_to_panic",
                }
            },
            {
                "prefect.deployments.steps.run_shell_script": {
                    "script": r"echo Don\'t Panic: {{ why_not_to_panic.stdout }}"
                }
            },
        ]
        step_outputs = await run_steps(steps, {})
        assert step_outputs == {
            "why_not_to_panic": {
                "stdout": "this is a test",
                "stderr": "",
            },
            "stdout": "Don't Panic: this is a test",
            "stderr": "",
        }

    async def test_run_steps_handles_error_gracefully(self, variables):
        steps = [
            {
                "prefect.deployments.steps.run_shell_script": {
                    "script": "echo 'this is a test'",
                    "id": "why_not_to_panic",
                }
            },
            {
                "nonexistent.module": {
                    "__fn": lambda x: x * 2,
                    "value": "{{ step_output_1 }}",
                }
            },
        ]
        with pytest.raises(StepExecutionError, match="nonexistent.module"):
            await run_steps(steps, {})

    async def test_run_steps_prints_step_names(
        self,
    ):
        mock_print = MagicMock()
        steps = [
            {
                "prefect.deployments.steps.run_shell_script": {
                    "script": "echo 'this is a test'",
                    "id": "why_not_to_panic",
                }
            },
            {
                "prefect.deployments.steps.run_shell_script": {
                    "script": (
                        'bash -c echo "Don\'t Panic: {{ why_not_to_panic.stdout }}"'
                    )
                }
            },
        ]
        await run_steps(steps, {}, print_function=mock_print)
        mock_print.assert_any_call(" > Running run_shell_script step...")

    async def test_run_steps_prints_deprecation_warnings(self, monkeypatch):
        def func(*args, **kwargs):
            warnings.warn("this is a warning", DeprecationWarning)
            return {}

        monkeypatch.setattr("prefect.deployments.steps.run_shell_script", func)

        mock_print = MagicMock()
        steps = [
            {
                "prefect.deployments.steps.run_shell_script": {
                    "script": "echo 'this is a test'",
                    "id": "why_not_to_panic",
                }
            },
        ]
        await run_steps(steps, {}, print_function=mock_print)
        mock_print.assert_any_call("this is a warning", style="yellow")

    async def test_run_steps_prints_prefect_deprecation_warnings(self, monkeypatch):
        def func(*args, **kwargs):
            warnings.warn("this is a warning", PrefectDeprecationWarning)
            return {}

        monkeypatch.setattr("prefect.deployments.steps.run_shell_script", func)

        mock_print = MagicMock()
        steps = [
            {
                "prefect.deployments.steps.run_shell_script": {
                    "script": "echo 'this is a test'",
                    "id": "why_not_to_panic",
                }
            },
        ]
        await run_steps(steps, {}, print_function=mock_print)
        mock_print.assert_any_call("this is a warning", style="yellow")

    async def test_run_steps_can_print_warnings_without_style(self, monkeypatch):
        def func(*args, **kwargs):
            warnings.warn("this is a warning", PrefectDeprecationWarning)
            return {}

        monkeypatch.setattr("prefect.deployments.steps.run_shell_script", func)

        # raise an exception when style is passed. exception type is irrelevant
        mock_print = MagicMock(
            side_effect=lambda *args, **kwargs: 1 / 0 if kwargs.get("style") else None
        )
        steps = [
            {
                "prefect.deployments.steps.run_shell_script": {
                    "script": "echo 'this is a test'",
                    "id": "why_not_to_panic",
                }
            },
        ]
        await run_steps(steps, {}, print_function=mock_print)
        mock_print.assert_any_call("this is a warning")


class MockCredentials:
    def __init__(
        self, token: str, username: Optional[str] = None, password: Optional[str] = None
    ):
        self.token = token
        self.username = username
        self.password = password

        self.data = {
            "value": {
                "token": self.token,
                "username": self.username,
                "password": self.password,
            }
        }

    async def save(self, name: str):
        pass

    async def load(self, name: str):
        return MockCredentials(token="mock-token")


@pytest.fixture
def git_repository_mock(monkeypatch):
    git_repository_mock = MagicMock()
    pull_code_mock = AsyncMock()
    git_repository_mock.return_value.pull_code = pull_code_mock
    git_repository_mock.return_value.destination = Path.cwd() / "repo"
    monkeypatch.setattr(
        "prefect.deployments.steps.pull.GitRepository",
        git_repository_mock,
    )
    return git_repository_mock


class TestSetWorkingDirectory:
    def test_set_working_directory_returns_absolute_path_with_relative_input(
        self, tmp_path: Path
    ):
        """Test that set_working_directory returns absolute path when given relative path."""
        # Create a subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        with tmpchdir(tmp_path):
            # Call set_working_directory with relative path
            result = set_working_directory("subdir")

            # Verify it returns the absolute path
            assert result["directory"] == str(subdir.resolve())
            assert os.path.isabs(result["directory"])
            assert os.getcwd() == str(subdir.resolve())

    def test_set_working_directory_returns_absolute_path_with_absolute_input(
        self, tmp_path: Path
    ):
        """Test that set_working_directory returns absolute path when given absolute path."""
        # Create a subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # Store original cwd to verify it's restored
        original_cwd = os.getcwd()

        # Call set_working_directory with absolute path
        result = set_working_directory(str(subdir))

        # Verify it returns the same absolute path
        assert result["directory"] == str(subdir.resolve())
        assert os.path.isabs(result["directory"])
        assert os.getcwd() == str(subdir.resolve())

        # Clean up by restoring the original working directory
        os.chdir(original_cwd)


class TestGitCloneStep:
    async def test_git_clone(self, git_repository_mock):
        output = await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://github.com/org/repo.git",
                }
            }
        )
        assert output["directory"] == "repo"
        git_repository_mock.assert_called_once_with(
            url="https://github.com/org/repo.git",
            credentials=None,
            branch=None,
            commit_sha=None,
            include_submodules=False,
            directories=None,
        )
        git_repository_mock.return_value.pull_code.assert_awaited_once()

    async def test_git_clone_include_submodules(self, git_repository_mock):
        output = await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://github.com/org/has-submodules.git",
                    "include_submodules": True,
                }
            }
        )
        assert output["directory"] == "repo"
        git_repository_mock.assert_called_once_with(
            url="https://github.com/org/has-submodules.git",
            credentials=None,
            branch=None,
            commit_sha=None,
            include_submodules=True,
            directories=None,
        )
        git_repository_mock.return_value.pull_code.assert_awaited_once()

    async def test_git_clone_with_access_token(self, git_repository_mock):
        await Secret(value="my-access-token").save(name="my-access-token")
        await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://github.com/org/repo.git",
                    "access_token": "{{ prefect.blocks.secret.my-access-token }}",
                }
            }
        )
        git_repository_mock.assert_called_once_with(
            url="https://github.com/org/repo.git",
            credentials={"access_token": "my-access-token"},
            branch=None,
            commit_sha=None,
            include_submodules=False,
            directories=None,
        )
        git_repository_mock.return_value.pull_code.assert_awaited_once()

    async def test_git_clone_with_credentials(self, git_repository_mock):
        class MockGitCredentials(Block):
            username: str
            password: str

        await MockGitCredentials(username="marvin42", password="hunter2").save(
            name="my-credentials"
        )
        await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://github.com/org/repo.git",
                    "credentials": (
                        "{{ prefect.blocks.mockgitcredentials.my-credentials }}"
                    ),
                }
            }
        )
        git_repository_mock.assert_called_once_with(
            url="https://github.com/org/repo.git",
            credentials={"username": "marvin42", "password": "hunter2"},
            branch=None,
            commit_sha=None,
            include_submodules=False,
            directories=None,
        )
        git_repository_mock.return_value.pull_code.assert_awaited_once()

    async def test_git_clone_retry(self, monkeypatch, caplog):
        mock_git_repo = MagicMock()
        mock_git_repo.return_value.pull_code = AsyncMock(
            side_effect=[
                RuntimeError("Octocat went out to lunch"),
                RuntimeError("Octocat is playing chess in the break room"),
                None,  # Successful on third attempt
            ]
        )
        mock_git_repo.return_value.destination.relative_to.return_value = "repo"
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.GitRepository", mock_git_repo
        )

        async def mock_sleep(seconds):
            pass

        monkeypatch.setattr("asyncio.sleep", mock_sleep)

        with caplog.at_level("WARNING"):
            result = await agit_clone(repository="https://github.com/org/repo.git")

        assert "Octocat went out to lunch" in caplog.text
        assert "Octocat is playing chess in the break room" in caplog.text

        assert result == {"directory": "repo"}

        expected_call = call(
            url="https://github.com/org/repo.git",
            credentials=None,
            branch=None,
            commit_sha=None,
            include_submodules=False,
            directories=None,
        )

        assert mock_git_repo.call_args_list == [expected_call]

    async def test_git_clone_with_commit_sha(self, git_repository_mock):
        output = await agit_clone(
            repository="https://github.com/org/repo.git",
            commit_sha="1234567890",
        )
        assert output["directory"] == "repo"
        git_repository_mock.assert_called_once_with(
            url="https://github.com/org/repo.git",
            credentials=None,
            branch=None,
            commit_sha="1234567890",
            include_submodules=False,
            directories=None,
        )
        git_repository_mock.return_value.pull_code.assert_awaited_once()

    async def test_agit_clone_basic(self, git_repository_mock):
        """Test basic async git clone functionality"""
        output = await agit_clone(repository="https://github.com/org/repo.git")

        assert output["directory"] == "repo"
        git_repository_mock.assert_called_once_with(
            url="https://github.com/org/repo.git",
            credentials=None,
            branch=None,
            commit_sha=None,
            include_submodules=False,
            directories=None,
        )
        git_repository_mock.return_value.pull_code.assert_awaited_once()

    async def test_agit_clone_with_all_options(self, git_repository_mock):
        """Test async git clone with all options specified"""
        await Secret(value="my-access-token").save(name="test-token")

        output = await agit_clone(
            repository="https://github.com/org/repo.git",
            branch="dev",
            include_submodules=True,
            access_token="my-access-token",
            directories=None,
        )

        assert output["directory"] == "repo"
        git_repository_mock.assert_called_once_with(
            url="https://github.com/org/repo.git",
            credentials={"access_token": "my-access-token"},
            branch="dev",
            commit_sha=None,
            include_submodules=True,
            directories=None,
        )
        git_repository_mock.return_value.pull_code.assert_awaited_once()

    async def test_agit_clone_with_credentials_block(self, git_repository_mock):
        """Test async git clone with credentials block"""

        class MockGitCredentials(Block):
            username: str
            password: str

        creds = MockGitCredentials(username="marvin42", password="hunter2")

        output = await agit_clone(
            repository="https://github.com/org/repo.git", credentials=creds
        )

        assert output["directory"] == "repo"
        git_repository_mock.assert_called_once_with(
            url="https://github.com/org/repo.git",
            credentials=creds,
            branch=None,
            commit_sha=None,
            include_submodules=False,
            directories=None,
        )
        git_repository_mock.return_value.pull_code.assert_awaited_once()

    async def test_agit_clone_raises_on_both_auth_methods(self):
        """Test that providing both access_token and credentials raises an error"""
        with pytest.raises(
            ValueError,
            match="Please provide either an access token or credentials but not both",
        ):
            await agit_clone(
                repository="https://github.com/org/repo.git",
                access_token="token",
                credentials=MagicMock(),
            )

    async def test_agit_clone_retry(self, monkeypatch, caplog):
        """Test retry behavior of async git clone"""
        mock_git_repo = MagicMock()
        mock_git_repo.return_value.pull_code = AsyncMock(
            side_effect=[
                RuntimeError("Network timeout"),
                RuntimeError("Server busy"),
                None,  # Success on third try
            ]
        )
        mock_git_repo.return_value.destination.relative_to.return_value = "repo"
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.GitRepository", mock_git_repo
        )

        async def mock_sleep(seconds):
            pass

        monkeypatch.setattr("asyncio.sleep", mock_sleep)

        with caplog.at_level("WARNING"):
            result = await agit_clone(repository="https://github.com/org/repo.git")

        assert result == {"directory": "repo"}
        assert mock_git_repo.return_value.pull_code.await_count == 3
        assert "Network timeout" in caplog.text
        assert "Server busy" in caplog.text

    async def test_agit_clone_with_commit_sha(self, git_repository_mock):
        output = await agit_clone(
            repository="https://github.com/org/repo.git",
            commit_sha="1234567890",
        )
        assert output["directory"] == "repo"
        git_repository_mock.assert_called_once_with(
            url="https://github.com/org/repo.git",
            credentials=None,
            branch=None,
            commit_sha="1234567890",
            include_submodules=False,
            directories=None,
        )
        git_repository_mock.return_value.pull_code.assert_awaited_once()

    async def test_agit_clone_via_steps(self, monkeypatch, caplog):
        """Test that async-only steps work when called via step syntax"""
        mock_git_repo = MagicMock()
        mock_git_repo.return_value.pull_code = AsyncMock(
            side_effect=[
                RuntimeError("Network timeout"),
                RuntimeError("Server busy"),
                None,  # Success on third try
            ]
        )
        mock_git_repo.return_value.destination.relative_to.return_value = "repo"
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.GitRepository", mock_git_repo
        )

        async def mock_sleep(seconds):
            pass

        monkeypatch.setattr("asyncio.sleep", mock_sleep)

        with caplog.at_level("WARNING"):
            result = await run_step(
                {
                    "prefect.deployments.steps.pull.agit_clone": {
                        "repository": "https://github.com/org/repo.git"
                    }
                }
            )

        assert result == {"directory": "repo"}
        assert mock_git_repo.return_value.pull_code.await_count == 3
        assert "Network timeout" in caplog.text
        assert "Server busy" in caplog.text

        expected_call = call(
            url="https://github.com/org/repo.git",
            credentials=None,
            branch=None,
            commit_sha=None,
            include_submodules=False,
            directories=None,
        )
        assert mock_git_repo.call_args_list == [expected_call]


class TestPullFromRemoteStorage:
    @pytest.fixture
    def remote_storage_mock(self, monkeypatch):
        remote_storage_mock = MagicMock()
        pull_code_mock = AsyncMock()
        remote_storage_mock.return_value.pull_code = pull_code_mock
        remote_storage_mock.return_value.destination = Path.cwd() / "bucket" / "folder"
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.RemoteStorage",
            remote_storage_mock,
        )
        return remote_storage_mock

    @pytest.fixture
    def mock_install_packages(self, monkeypatch):
        mock_install_packages = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.core.install_packages",
            mock_install_packages,
        )
        return mock_install_packages

    @pytest.fixture
    def import_module_mock(self, monkeypatch):
        import_module_mock = MagicMock(side_effect=ImportError())
        monkeypatch.setattr(
            "prefect.deployments.steps.core.import_module",
            import_module_mock,
        )
        return import_module_mock

    async def test_pull_from_remote_storage(
        self, remote_storage_mock, mock_install_packages, import_module_mock
    ):
        output = await run_step(
            {
                "prefect.deployments.steps.pull_from_remote_storage": {
                    "requires": "s3fs<3.0",
                    "url": "s3://bucket/folder",
                    "key": "my-access-key-id",
                    "secret": "my-secret-access-key",
                }
            }
        )
        assert output["directory"] == "bucket/folder"
        import_module_mock.assert_called_once_with("s3fs")
        mock_install_packages.assert_called_once_with(["s3fs<3.0"], stream_output=True)
        remote_storage_mock.assert_called_once_with(
            "s3://bucket/folder",
            key="my-access-key-id",
            secret="my-secret-access-key",
        )
        remote_storage_mock.return_value.pull_code.assert_awaited_once()


class TestRunShellScript:
    async def test_run_shell_script_single_command(self, capsys):
        result = await run_shell_script("echo Hello World", stream_output=True)
        assert result["stdout"] == "Hello World"
        assert result["stderr"] == ""

        # Validate the output was streamed to the console
        out, err = capsys.readouterr()
        assert out.strip() == "Hello World"
        assert err == ""

    async def test_run_shell_script_multiple_commands(self, capsys):
        script = """
        echo First Line
        echo Second Line
        """
        result = await run_shell_script(script, stream_output=True)
        assert result["stdout"] == "First Line\nSecond Line"
        assert result["stderr"] == ""

        # Validate the output was streamed to the console
        out, err = capsys.readouterr()
        assert out.strip() == "First Line\nSecond Line"
        assert err == ""

    @pytest.mark.skipif(
        sys.platform == "win32", reason="stderr redirect does not work on Windows"
    )
    async def test_run_shell_script_stderr(self, capsys):
        script = "bash -c '>&2 echo Error Message'"
        result = await run_shell_script(script, stream_output=True)
        assert result["stdout"] == ""
        assert result["stderr"] == "Error Message"

        # Validate the error was streamed to the console
        out, err = capsys.readouterr()
        assert out == ""
        assert err.strip() == "Error Message"

    @pytest.mark.parametrize(
        "script,expected",
        [
            ("bash -c 'echo $TEST_ENV_VAR'", "Test Value"),
            ("echo $TEST_ENV_VAR", "$TEST_ENV_VAR"),
        ],
    )
    async def test_run_shell_script_with_env(self, script, expected, capsys):
        result = await run_shell_script(
            script, env={"TEST_ENV_VAR": "Test Value"}, stream_output=True
        )
        assert result["stdout"] == expected
        assert result["stderr"] == ""

        # Validate the output was streamed to the console
        out, err = capsys.readouterr()
        assert out.strip() == expected
        assert err == ""

    @pytest.mark.parametrize(
        "script",
        [
            "echo $DUMMY_ENV_VAR",
            "bash -c 'echo $DUMMY_ENV_VAR'",
        ],
    )
    async def test_run_shell_script_expand_env(self, script, capsys, set_dummy_env_var):
        result = await run_shell_script(
            script,
            expand_env_vars=True,
            stream_output=True,
        )

        assert result["stdout"] == "dummy"
        assert result["stderr"] == ""

    async def test_run_shell_script_no_expand_env(self, capsys, set_dummy_env_var):
        result = await run_shell_script(
            "echo $DUMMY_ENV_VAR",
            stream_output=True,
        )

        assert result["stdout"] == "$DUMMY_ENV_VAR"
        assert result["stderr"] == ""

    async def test_run_shell_script_no_output(self, capsys):
        result = await run_shell_script("echo Hello World", stream_output=False)
        assert result["stdout"] == "Hello World"
        assert result["stderr"] == ""

        # Validate nothing was streamed to the console
        out, err = capsys.readouterr()
        assert out == ""
        assert err == ""

    async def test_run_shell_script_in_directory(self):
        parent_dir = str(Path.cwd().parent)
        result = await run_shell_script(
            "pwd", directory=parent_dir, stream_output=False
        )
        assert result["stdout"] == parent_dir
        assert result["stderr"] == ""

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="_open_anyio_process errors when mocking OS in test context",
    )
    async def test_run_shell_script_split_on_windows(self, monkeypatch):
        # return type needs to be mocked to avoid TypeError
        shex_split_mock = MagicMock(return_value=["echo", "Hello", "World"])
        monkeypatch.setattr(
            "prefect.deployments.steps.utility.shlex.split",
            shex_split_mock,
        )
        result = await run_shell_script("echo Hello World")
        # validates that command is parsed as non-posix
        shex_split_mock.assert_called_once_with("echo Hello World", posix=False)
        assert result["stdout"] == "Hello World"
        assert result["stderr"] == ""


class MockProcess:
    def __init__(self, returncode=0):
        self.returncode = returncode

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def wait(self):
        pass


class TestPipInstallRequirements:
    async def test_pip_install_reqs_runs_expected_command(self, monkeypatch):
        open_process_mock = MagicMock(return_value=MockProcess(0))
        monkeypatch.setattr(
            "prefect.deployments.steps.utility.open_process",
            open_process_mock,
        )

        mock_stream_capture = AsyncMock()

        monkeypatch.setattr(
            "prefect.deployments.steps.utility._stream_capture_process_output",
            mock_stream_capture,
        )

        await run_step(
            {
                "prefect.deployments.steps.pip_install_requirements": {
                    "id": "pip-install-step"
                }
            }
        )

        open_process_mock.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=None,
            stderr=ANY,
            stdout=ANY,
        )

    async def test_pip_install_reqs_custom_requirements_file(self, monkeypatch):
        open_process_mock = MagicMock(return_value=MockProcess(0))
        monkeypatch.setattr(
            "prefect.deployments.steps.utility.open_process",
            open_process_mock,
        )

        mock_stream_capture = AsyncMock()

        monkeypatch.setattr(
            "prefect.deployments.steps.utility._stream_capture_process_output",
            mock_stream_capture,
        )

        await run_step(
            {
                "prefect.deployments.steps.pip_install_requirements": {
                    "id": "pip-install-step",
                    "requirements_file": "dev-requirements.txt",
                }
            }
        )

        open_process_mock.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "-r", "dev-requirements.txt"],
            cwd=None,
            stderr=ANY,
            stdout=ANY,
        )

    async def test_pip_install_reqs_with_directory_step_output_succeeds(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        open_process_mock = MagicMock(return_value=MockProcess(0))
        monkeypatch.setattr(
            "prefect.deployments.steps.utility.open_process",
            open_process_mock,
        )

        mock_stream_capture = AsyncMock()

        monkeypatch.setattr(
            "prefect.deployments.steps.utility._stream_capture_process_output",
            mock_stream_capture,
        )

        steps = [
            {
                "prefect.deployments.steps.git_clone": {
                    "id": "clone-step",
                    "repository": "https://github.com/PrefectHQ/hello-projects.git",
                }
            },
            {
                "prefect.deployments.steps.pip_install_requirements": {
                    "id": "pip-install-step",
                    "directory": "{{ clone-step.directory }}",
                    "requirements_file": "requirements.txt",
                }
            },
        ]

        step_outputs = {
            "clone-step": {"directory": "hello-projects"},
            "directory": "hello-projects",
            "pip-install-step": {"stdout": "", "stderr": ""},
            "stdout": "",
            "stderr": "",
        }

        open_process_mock.run.return_value = MagicMock(**step_outputs)

        with tmpchdir(tmp_path):
            output = await run_steps(steps)

        assert output == step_outputs

        open_process_mock.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            cwd="hello-projects",
            stderr=ANY,
            stdout=ANY,
        )

    async def test_pip_install_fails_on_error(self, monkeypatch):
        open_process_mock = MagicMock(return_value=MockProcess(1))
        monkeypatch.setattr(
            "prefect.deployments.steps.utility.open_process",
            open_process_mock,
        )

        mock_stream_capture = AsyncMock()
        mock_stream_capture.side_effect = lambda *args, **kwargs: kwargs[
            "stderr_sink"
        ].write(
            "ERROR: Could not open requirements file: [Errno 2] No such file or directory: 'doesnt-exist.txt'"
        )

        monkeypatch.setattr(
            "prefect.deployments.steps.utility._stream_capture_process_output",
            mock_stream_capture,
        )
        with pytest.raises(RuntimeError) as exc:
            await run_step(
                {
                    "prefect.deployments.steps.pip_install_requirements": {
                        "id": "pip-install-step",
                        "requirements_file": "doesnt-exist.txt",
                    }
                }
            )
        assert (
            "pip_install_requirements failed with error code 1: ERROR: Could not open "
            "requirements file: [Errno 2] No such file or directory: "
            "'doesnt-exist.txt'" in str(exc.value)
        )


class TestPullWithBlock:
    @pytest.fixture
    async def test_block(self, monkeypatch, tmp_path):
        monkeypatch.chdir(str(tmp_path))  # ensures never writes to active directory

        class FakeStorageBlock(Block):
            _block_type_slug = "fake-storage-block"

            code: str = dedent(
                """\
                from prefect import flow

                @flow
                def test_flow():
                    return 1
                """
            )

            async def get_directory(self, local_path: str):
                (Path(local_path) / "flows.py").write_text(self.code)

        block = FakeStorageBlock()
        await block.save("test-block")
        return block

    async def test_normal_operation(self, test_block: Block):
        """
        A block type slug and a block document name corresponding
        to a block with the get_directory method can be used
        to pull code into the current working path.
        """
        try:
            output = await run_step(
                {
                    "prefect.deployments.steps.pull_with_block": {
                        "block_type_slug": test_block.get_block_type_slug(),
                        "block_document_name": test_block._block_document_name,
                    }
                }
            )
            assert "directory" in output
            assert Path(f"{output['directory']}/flows.py").read_text() == dedent(
                """\
                from prefect import flow

                @flow
                def test_flow():
                    return 1
                """
            )
        finally:
            if "output" in locals() and "directory" in output:
                shutil.rmtree(f"{output['directory']}")

    async def test_block_not_found(self, caplog):
        """
        When a `pull_with_block` step is run with a block type slug
        and block document name that can't be resolved, `run_step`
        should raise and log a message.
        """
        with pytest.raises(ValueError):
            await run_step(
                {
                    "prefect.deployments.steps.pull_with_block": {
                        "block_type_slug": "in-the",
                        "block_document_name": "wind",
                    }
                }
            )

        assert "Unable to load block 'in-the/wind'" in caplog.text

    async def test_incorrect_type_of_block(self, caplog):
        """
        When a `pull_with_block` step is run with a block that doesn't
        have a `get_directory` method, `run_step` should raise and log
        a message.
        """

        class Wrong(Block):
            square_peg: str = "round_hole"

        block = Wrong()
        await block.save("test-block")

        with pytest.raises(ValueError):
            await run_step(
                {
                    "prefect.deployments.steps.pull_with_block": {
                        "block_type_slug": block.get_block_type_slug(),
                        "block_document_name": block._block_document_name,
                    }
                }
            )

        assert (
            "Unable to create storage adapter for block"
            f" '{block.get_block_type_slug()}/{block._block_document_name}"
            in caplog.text
        )
