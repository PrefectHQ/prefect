import sys
import warnings
from pathlib import Path
from unittest.mock import ANY

import pytest

from prefect._internal.compatibility.deprecated import PrefectDeprecationWarning
from prefect.blocks.system import Secret
from prefect.client.orchestration import PrefectClient
from prefect.deployments.steps import run_step
from prefect.deployments.steps.core import StepExecutionError, run_steps
from prefect.deployments.steps.utility import run_shell_script
from prefect.testing.utilities import AsyncMock, MagicMock


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
    def __init__(self, token: str, username: str = None, password: str = None):
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


class TestGitCloneStep:
    async def test_git_clone(self, monkeypatch):
        subprocess_mock = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.subprocess",
            subprocess_mock,
        )
        output = await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://github.com/org/repo.git",
                }
            }
        )
        assert output["directory"] == "repo"
        subprocess_mock.check_call.assert_called_once_with(
            [
                "git",
                "clone",
                "https://github.com/org/repo.git",
                "--depth",
                "1",
            ],
            shell=False,
            stderr=ANY,
            stdout=ANY,
        )

    async def test_deprecated_git_clone_project(self, monkeypatch):
        subprocess_mock = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.subprocess",
            subprocess_mock,
        )
        with pytest.warns(DeprecationWarning):
            output = await run_step(
                {
                    "prefect.projects.steps.git_clone_project": {
                        "repository": "https://github.com/org/repo.git",
                    }
                }
            )
        assert output["directory"] == "repo"
        subprocess_mock.check_call.assert_called_once_with(
            [
                "git",
                "clone",
                "https://github.com/org/repo.git",
                "--depth",
                "1",
            ],
            shell=False,
            stderr=ANY,
            stdout=ANY,
        )

    async def test_git_clone_include_submodules(self, monkeypatch):
        subprocess_mock = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.subprocess",
            subprocess_mock,
        )
        output = await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://github.com/org/has-submodules.git",
                    "include_submodules": True,
                }
            }
        )
        assert output["directory"] == "has-submodules"
        subprocess_mock.check_call.assert_called_once_with(
            [
                "git",
                "clone",
                "https://github.com/org/has-submodules.git",
                "--recurse-submodules",
                "--depth",
                "1",
            ],
            shell=False,
            stderr=ANY,
            stdout=ANY,
        )

    async def test_git_clone_errors_obscure_access_token(self):
        with pytest.raises(RuntimeError) as exc:
            await run_step(
                {
                    "prefect.deployments.steps.git_clone": {
                        "repository": "https://github.com/PrefectHQ/prefect.git",
                        "branch": "definitely-does-not-exist-123",
                        "access_token": None,
                    }
                }
            )
        # prove by default command shows up
        assert (
            "Command '['git', 'clone', 'https://github.com/PrefectHQ/prefect.git',"
            " '-b', 'definitely-does-not-exist-123', '--depth', '1']"
            in str(exc.getrepr())
        )

        with pytest.raises(RuntimeError) as exc:
            # we uppercase the token because this test definition does show up in the exception traceback
            await run_step(
                {
                    "prefect.deployments.steps.git_clone": {
                        "repository": "https://github.com/PrefectHQ/prefect.git",
                        "branch": "definitely-does-not-exist-123",
                        "access_token": "super-secret-42".upper(),
                    }
                }
            )
        assert "super-secret-42".upper() not in str(exc.getrepr())

    @pytest.mark.asyncio
    async def test_git_clone_with_valid_credentials_block_succeeds(self, monkeypatch):
        mock_subprocess = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.subprocess",
            mock_subprocess,
        )
        blocks = {
            "github-credentials": {
                "my-github-creds-block": MockCredentials("mock-token")
            }
        }

        async def mock_read_block_document(self, name: str, block_type_slug: str):
            return blocks[block_type_slug][name]

        monkeypatch.setattr(
            "prefect.client.orchestration.PrefectClient.read_block_document_by_name",
            mock_read_block_document,
        )

        await MockCredentials("mock-token").save("my-github-creds-block")

        output = await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://github.com/org/repo.git",
                    "credentials": (
                        "{{ prefect.blocks.github-credentials.my-github-creds-block }}"
                    ),
                }
            }
        )

        assert output["directory"] == "repo"
        mock_subprocess.check_call.assert_called_once_with(
            [
                "git",
                "clone",
                "https://mock-token@github.com/org/repo.git",
                "--depth",
                "1",
            ],
            shell=False,
            stderr=ANY,
            stdout=ANY,
        )

    @pytest.mark.asyncio
    async def test_github_clone_with_invalid_credentials_block_raises(
        self, monkeypatch
    ):
        blocks = {
            "github-credentials": {
                "my-github-creds-block": MockCredentials("mock-token")
            }
        }

        async def mock_read_block_document(self, name: str, block_type_slug: str):
            return blocks[block_type_slug][name]

        monkeypatch.setattr(
            "prefect.client.orchestration.PrefectClient.read_block_document_by_name",
            mock_read_block_document,
        )

        with pytest.raises(KeyError, match="invalid-block"):
            await run_step(
                {
                    "prefect.deployments.steps.git_clone": {
                        "repository": "https://github.com/org/repo.git",
                        "credentials": (
                            "{{ prefect.blocks.github-credentials.invalid-block }}"
                        ),
                    }
                }
            )

    @pytest.mark.asyncio
    async def test_git_clone_with_token_and_credentials_raises(self, monkeypatch):
        blocks = {
            "github-credentials": {
                "my-github-creds-block": MockCredentials("mock-token")
            }
        }

        async def mock_read_block_document(self, name: str, block_type_slug: str):
            return blocks[block_type_slug][name]

        monkeypatch.setattr(
            "prefect.client.orchestration.PrefectClient.read_block_document_by_name",
            mock_read_block_document,
        )

        with pytest.raises(
            ValueError,
            match="Please provide either an access token or credentials but not both",
        ):
            await run_step(
                {
                    "prefect.deployments.steps.git_clone": {
                        "repository": "https://github.com/org/repo.git",
                        "access_token": "my-token",
                        "credentials": (
                            "{{ prefect.blocks.github-credentials.my-github-creds-block }}"
                        ),
                    }
                }
            )

    @pytest.mark.parametrize(
        "access_token", ["example-token", "x-token-auth:example-token"]
    )
    async def test_git_clone_with_bitbucket_access_token(
        self, access_token, monkeypatch
    ):
        subprocess_mock = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.subprocess",
            subprocess_mock,
        )
        output = await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://bitbucket.org/org/repo.git",
                    "access_token": access_token,
                }
            }
        )
        assert output["directory"] == "repo"
        subprocess_mock.check_call.assert_called_once_with(
            [
                "git",
                "clone",
                "https://x-token-auth:example-token@bitbucket.org/org/repo.git",
                "--depth",
                "1",
            ],
            shell=False,
            stderr=ANY,
            stdout=ANY,
        )

    async def test_git_clone_with_bitbucket_credentials_block(self, monkeypatch):
        mock_subprocess = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.subprocess",
            mock_subprocess,
        )
        blocks = {
            "bitbucket-credentials": {
                "my-bitbucket-creds-block": MockCredentials("mock-token")
            }
        }

        async def mock_read_block_document(self, name: str, block_type_slug: str):
            return blocks[block_type_slug][name]

        monkeypatch.setattr(
            "prefect.client.orchestration.PrefectClient.read_block_document_by_name",
            mock_read_block_document,
        )

        await MockCredentials("x-token-auth:mock-token").save(
            "my-bitbucket-creds-block"
        )

        output = await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://bitbucket.org/org/repo.git",
                    "credentials": (
                        "{{ prefect.blocks.bitbucket-credentials.my-bitbucket-creds-block }}"
                    ),
                }
            }
        )

        assert output["directory"] == "repo"
        mock_subprocess.check_call.assert_called_once_with(
            [
                "git",
                "clone",
                "https://x-token-auth:mock-token@bitbucket.org/org/repo.git",
                "--depth",
                "1",
            ],
            shell=False,
            stderr=ANY,
            stdout=ANY,
        )

    async def test_git_clone_with_bitbucket_credentials_block_old_format(
        self, monkeypatch
    ):
        mock_subprocess = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.subprocess",
            mock_subprocess,
        )
        blocks = {
            "bitbucket-credentials": {
                "my-bitbucket-creds-block": MockCredentials("mock-token")
            }
        }

        async def mock_read_block_document(self, name: str, block_type_slug: str):
            return blocks[block_type_slug][name]

        monkeypatch.setattr(
            "prefect.client.orchestration.PrefectClient.read_block_document_by_name",
            mock_read_block_document,
        )

        await MockCredentials("mock-token").save("my-bitbucket-creds-block")

        output = await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://bitbucket.org/org/repo.git",
                    "credentials": (
                        "{{ prefect.blocks.bitbucket-credentials.my-bitbucket-creds-block }}"
                    ),
                }
            }
        )

        assert output["directory"] == "repo"
        mock_subprocess.check_call.assert_called_once_with(
            [
                "git",
                "clone",
                "https://x-token-auth:mock-token@bitbucket.org/org/repo.git",
                "--depth",
                "1",
            ],
            shell=False,
            stderr=ANY,
            stdout=ANY,
        )

    async def test_git_clone_with_bitbucket_public_repo(self, monkeypatch):
        subprocess_mock = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.subprocess",
            subprocess_mock,
        )
        output = await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://bitbucket.org/org/repo.git",
                }
            }
        )
        assert output["directory"] == "repo"
        subprocess_mock.check_call.assert_called_once_with(
            [
                "git",
                "clone",
                "https://bitbucket.org/org/repo.git",
                "--depth",
                "1",
            ],
            shell=False,
            stderr=ANY,
            stdout=ANY,
        )

    @pytest.mark.parametrize(
        "access_token", ["x-token-auth:example-token", "username:example-token"]
    )
    async def test_git_clone_with_bitbucket_server_repo_with_access_token(
        self, monkeypatch, access_token
    ):
        subprocess_mock = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.subprocess",
            subprocess_mock,
        )
        output = await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": (
                        "https://bitbucketserver.com/scm/projectname/teamsinspace.git"
                    ),
                    "access_token": access_token,
                }
            }
        )

        formatted_token = (
            f"x-token-auth:{access_token}" if ":" not in access_token else access_token
        )

        assert output["directory"] == "teamsinspace"
        subprocess_mock.check_call.assert_called_once_with(
            [
                "git",
                "clone",
                f"https://{formatted_token}@bitbucketserver.com/scm/projectname/teamsinspace.git",
                "--depth",
                "1",
            ],
            shell=False,
            stderr=ANY,
            stdout=ANY,
        )

    async def test_git_clone_with_bitbucket_server_repo_with_invalid_access_token_raises(
        self, monkeypatch
    ):
        subprocess_mock = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.subprocess",
            subprocess_mock,
        )
        with pytest.raises(
            ValueError,
            match=(
                "Please prefix your BitBucket Server access_token with a username, e.g."
                " 'username:token'"
            ),
        ):
            await run_step(
                {
                    "prefect.deployments.steps.git_clone": {
                        "repository": "https://bitbucketserver.com/scm/projectname/teamsinspace.git",
                        "access_token": "example-token",
                    }
                }
            )

    @pytest.mark.parametrize("token", (["username:example-token", "example-token"]))
    async def test_git_clone_with_bitbucket_server_repo_with_valid_bitbucket_credentials_block(
        self, monkeypatch, token
    ):
        mock_subprocess = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.subprocess",
            mock_subprocess,
        )
        blocks = {
            "bitbucket-credentials": {
                "my-bitbucket-creds-block": MockCredentials(
                    token=token, username="username"
                )
            }
        }

        async def mock_read_block_document(self, name: str, block_type_slug: str):
            return blocks[block_type_slug][name]

        monkeypatch.setattr(
            "prefect.client.orchestration.PrefectClient.read_block_document_by_name",
            mock_read_block_document,
        )

        await MockCredentials(token=token, username="username").save(
            "my-bitbucket-creds-block"
        )

        output = await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": (
                        "https://bitbucketserver.com/scm/projectname/teamsinspace.git"
                    ),
                    "credentials": (
                        "{{ prefect.blocks.bitbucket-credentials.my-bitbucket-creds-block }}"
                    ),
                }
            }
        )

        assert output["directory"] == "teamsinspace"
        mock_subprocess.check_call.assert_called_once_with(
            [
                "git",
                "clone",
                "https://username:example-token@bitbucketserver.com/scm/projectname/teamsinspace.git",
                "--depth",
                "1",
            ],
            shell=False,
            stderr=ANY,
            stdout=ANY,
        )

    async def test_git_clone_with_bitbucket_server_repo_with_invalid_bitbucket_credentials_block_raises(
        self, monkeypatch
    ):
        pass

    @pytest.mark.parametrize("access_token", ["example-token", "oauth2:example-token"])
    async def test_git_clone_with_gitlab_access_token(self, access_token, monkeypatch):
        subprocess_mock = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.subprocess",
            subprocess_mock,
        )
        output = await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://gitlab.com/org/repo.git",
                    "access_token": access_token,
                }
            }
        )
        assert output["directory"] == "repo"
        subprocess_mock.check_call.assert_called_once_with(
            [
                "git",
                "clone",
                "https://oauth2:example-token@gitlab.com/org/repo.git",
                "--depth",
                "1",
            ],
            shell=False,
            stderr=ANY,
            stdout=ANY,
        )

    async def test_git_clone_with_gitlab_public_repo(self, monkeypatch):
        subprocess_mock = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.subprocess",
            subprocess_mock,
        )
        output = await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://gitlab.com/org/repo.git",
                }
            }
        )
        assert output["directory"] == "repo"
        subprocess_mock.check_call.assert_called_once_with(
            [
                "git",
                "clone",
                "https://gitlab.com/org/repo.git",
                "--depth",
                "1",
            ],
            shell=False,
            stderr=ANY,
            stdout=ANY,
        )

    async def test_git_clone_with_gitlab_credentials_block(self, monkeypatch):
        mock_subprocess = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.subprocess",
            mock_subprocess,
        )
        blocks = {
            "gitlab-credentials": {
                "my-gitlab-creds-block": MockCredentials("mock-token")
            }
        }

        async def mock_read_block_document(self, name: str, block_type_slug: str):
            return blocks[block_type_slug][name]

        monkeypatch.setattr(
            "prefect.client.orchestration.PrefectClient.read_block_document_by_name",
            mock_read_block_document,
        )

        await MockCredentials("oauth2:mock-token").save("my-gitlab-creds-block")

        output = await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://gitlab.com/org/repo.git",
                    "credentials": (
                        "{{ prefect.blocks.gitlab-credentials.my-gitlab-creds-block }}"
                    ),
                }
            }
        )

        assert output["directory"] == "repo"
        mock_subprocess.check_call.assert_called_once_with(
            [
                "git",
                "clone",
                "https://oauth2:mock-token@gitlab.com/org/repo.git",
                "--depth",
                "1",
            ],
            shell=False,
            stderr=ANY,
            stdout=ANY,
        )

    async def test_git_clone_with_gitlab_credentials_block_old_format(
        self, monkeypatch
    ):
        mock_subprocess = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.subprocess",
            mock_subprocess,
        )
        blocks = {
            "gitlab-credentials": {
                "my-gitlab-creds-block": MockCredentials("mock-token")
            }
        }

        async def mock_read_block_document(self, name: str, block_type_slug: str):
            return blocks[block_type_slug][name]

        monkeypatch.setattr(
            "prefect.client.orchestration.PrefectClient.read_block_document_by_name",
            mock_read_block_document,
        )

        await MockCredentials("mock-token").save("my-gitlab-creds-block")

        output = await run_step(
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://gitlab.com/org/repo.git",
                    "credentials": (
                        "{{ prefect.blocks.gitlab-credentials.my-gitlab-creds-block }}"
                    ),
                }
            }
        )

        assert output["directory"] == "repo"
        mock_subprocess.check_call.assert_called_once_with(
            [
                "git",
                "clone",
                "https://oauth2:mock-token@gitlab.com/org/repo.git",
                "--depth",
                "1",
            ],
            shell=False,
            stderr=ANY,
            stdout=ANY,
        )


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


class TestPipInstallRequirements:
    async def test_pip_install_reqs_runs_expected_command(self, monkeypatch):
        open_process_mock = MagicMock()
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
        open_process_mock = MagicMock()
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
        self, monkeypatch
    ):
        subprocess_mock = MagicMock()
        monkeypatch.setattr(
            "prefect.deployments.steps.pull.subprocess",
            subprocess_mock,
        )

        open_process_mock = MagicMock()
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

        output = await run_steps(steps)

        assert output == step_outputs

        open_process_mock.assert_called_once_with(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                "requirements.txt",
            ],
            cwd="hello-projects",
            stderr=ANY,
            stdout=ANY,
        )
