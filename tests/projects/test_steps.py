import pytest

from prefect import Flow
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
        assert isinstance(flow, Flow)
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
        assert isinstance(flow, Flow)
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
        assert isinstance(flow, Flow)
        assert flow.name == "test_value_1:test_value_2"
        assert flow.fn(None) == 42
