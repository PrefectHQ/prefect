import pytest

from prefect import Flow
from prefect.blocks.system import Secret
from prefect.projects.steps import run_step


class TestRunStep:
    async def test_run_step_runs_importable_functions(self):
        flow = run_step({"prefect.flow": {"__fn": lambda x: 42, "name": "test-name"}})
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
