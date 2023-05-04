import pytest

import prefect
from prefect.blocks.system import Secret
from prefect.client.orchestration import PrefectClient
from prefect.projects.steps import run_step


@pytest.fixture
async def variables(orion_client: PrefectClient):
    await orion_client._client.post(
        "/variables/", json={"name": "test_variable_1", "value": "test_value_1"}
    )
    await orion_client._client.post(
        "/variables/", json={"name": "test_variable_2", "value": "test_value_2"}
    )


class TestRunStep:
    async def test_run_step_runs_importable_functions(self):
        flow = await run_step(
            {"prefect.flow": {"__fn": lambda x: 42, "name": "test-name"}}
        )
        assert isinstance(flow, prefect.Flow)
        assert flow.name == "test-name"
        assert flow.fn(None) == 42

    async def test_run_step_errors_with_improper_format(self):
        with pytest.raises(ValueError, match="unexpected"):
            await run_step(
                {"prefect.flow": {"__fn": lambda x: 42, "name": "test-name"}, "jedi": 0}
            )

    async def test_run_step_resolves_block_document_references_before_running(self):
        await Secret(value="secret-name").save(name="test-secret")

        flow = await run_step(
            {
                "prefect.flow": {
                    "__fn": lambda x: 42,
                    "name": "{{ prefect.blocks.secret.test-secret }}",
                }
            }
        )
        assert isinstance(flow, prefect.Flow)
        assert flow.name == "secret-name"
        assert flow.fn(None) == 42

    async def test_run_step_resolves_variables_before_running(self, variables):
        flow = await run_step(
            {
                "prefect.flow": {
                    "__fn": lambda x: 42,
                    "name": (
                        "{{ prefect.variables.test_variable_1 }}:{{"
                        " prefect.variables.test_variable_2 }}"
                    ),
                }
            }
        )
        assert isinstance(flow, prefect.Flow)
        assert flow.name == "test_value_1:test_value_2"
        assert flow.fn(None) == 42

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


class TestGitCloneStep:
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
