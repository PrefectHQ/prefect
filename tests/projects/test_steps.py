from pathlib import Path
import sys
from unittest.mock import MagicMock, ANY
import pytest

from prefect.blocks.system import Secret
from prefect.client.orchestration import PrefectClient
from prefect.projects.steps import run_step

from prefect.projects.steps.utility import run_shell_script
from prefect.projects.steps.core import StepExecutionError, run_steps


@pytest.fixture
async def variables(prefect_client: PrefectClient):
    await prefect_client._client.post(
        "/variables/", json={"name": "test_variable_1", "value": "test_value_1"}
    )
    await prefect_client._client.post(
        "/variables/", json={"name": "test_variable_2", "value": "test_value_2"}
    )


class TestRunStep:
    async def test_run_step_runs_importable_functions(self):
        output = await run_step(
            {
                "prefect.projects.steps.run_shell_script": {
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
                    "prefect.projects.steps.run_shell_script": {
                        "script": "echo 'this is a test'"
                    },
                    "jedi": 0,
                }
            )

    async def test_run_step_resolves_block_document_references_before_running(self):
        await Secret(value="echo 'I am a secret!'").save(name="test-secret")

        output = await run_step(
            {
                "prefect.projects.steps.run_shell_script": {
                    "script": "{{ prefect.blocks.secret.test-secret }}",
                }
            }
        )
        assert isinstance(output, dict)
        assert output == {
            "stdout": "I am a secret!",
            "stderr": "",
        }

    async def test_run_step_resolves_variables_before_running(self, variables):
        output = await run_step(
            {
                "prefect.projects.steps.run_shell_script": {
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
                "prefect.projects.steps.run_shell_script": {
                    "script": "echo 'this is a test'",
                    "id": "why_not_to_panic",
                }
            },
            {
                "prefect.projects.steps.run_shell_script": {
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
                "prefect.projects.steps.run_shell_script": {
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
                "prefect.projects.steps.run_shell_script": {
                    "script": "echo 'this is a test'",
                    "id": "why_not_to_panic",
                }
            },
            {
                "prefect.projects.steps.run_shell_script": {
                    "script": (
                        'bash -c echo "Don\'t Panic: {{ why_not_to_panic.stdout }}"'
                    )
                }
            },
        ]
        await run_steps(steps, {}, print_function=mock_print)
        mock_print.assert_any_call(" > Running run_shell_script step...")


class TestGitCloneStep:
    async def test_git_clone(self, monkeypatch):
        subprocess_mock = MagicMock()
        monkeypatch.setattr(
            "prefect.projects.steps.pull.subprocess",
            subprocess_mock,
        )
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
            "prefect.projects.steps.pull.subprocess",
            subprocess_mock,
        )
        output = await run_step(
            {
                "prefect.projects.steps.git_clone_project": {
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
                    "prefect.projects.steps.git_clone_project": {
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
                    "prefect.projects.steps.git_clone_project": {
                        "repository": "https://github.com/PrefectHQ/prefect.git",
                        "branch": "definitely-does-not-exist-123",
                        "access_token": "super-secret-42".upper(),
                    }
                }
            )
        assert "super-secret-42".upper() not in str(exc.getrepr())


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

    async def test_run_shell_script_with_env(self, capsys):
        script = "bash -c 'echo $TEST_ENV_VAR'"
        result = await run_shell_script(
            script, env={"TEST_ENV_VAR": "Test Value"}, stream_output=True
        )
        assert result["stdout"] == "Test Value"
        assert result["stderr"] == ""

        # Validate the output was streamed to the console
        out, err = capsys.readouterr()
        assert out.strip() == "Test Value"
        assert err == ""

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
