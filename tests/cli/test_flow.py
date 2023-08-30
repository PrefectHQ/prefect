import datetime

import pytest

from prefect.client.orchestration import PrefectClient
from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import AsyncMock
from prefect.utilities.asyncutils import run_sync_in_worker_thread


class TestFlowServe:
    """
    These tests ensure that the `prefect flow serve` interacts with Runner
    in the expected way. Behavior such as flow run
    execution and cancellation are tested in test_runner.py.
    """

    @pytest.fixture
    async def mock_runner_start(self, monkeypatch):
        mock = AsyncMock()
        monkeypatch.setattr("prefect.cli.flow.Runner.start", mock)
        return mock

    def test_flow_serve_cli_requires_entrypoint(self):
        invoke_and_assert(
            command=["flow", "serve"],
            expected_code=2,
            expected_output_contains=[
                "Missing argument 'ENTRYPOINT'.",
            ],
        )

    async def test_flow_serve_cli_creates_deployment(
        self, prefect_client: PrefectClient, mock_runner_start: AsyncMock
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=["flow", "serve", "flows/hello_world.py:hello", "--name", "test"],
            expected_code=0,
            expected_output_contains=[
                "Your flow 'hello' is being served and polling for scheduled runs!",
                "To trigger a run for this flow, use the following command",
                "$ prefect deployment run 'hello/test'",
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(name="hello/test")

        assert deployment is not None
        assert deployment.name == "test"
        assert deployment.entrypoint == "flows/hello_world.py:hello"

        mock_runner_start.assert_called_once()

    async def test_flow_serve_cli_accepts_interval(
        self, prefect_client: PrefectClient, mock_runner_start
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow",
                "serve",
                "flows/hello_world.py:hello",
                "--name",
                "test",
                "--interval",
                "3600",
            ],
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(name="hello/test")

        assert deployment.schedule.interval == datetime.timedelta(seconds=3600)

    async def test_flow_serve_cli_accepts_cron(
        self, prefect_client: PrefectClient, mock_runner_start
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow",
                "serve",
                "flows/hello_world.py:hello",
                "--name",
                "test",
                "--cron",
                "* * * * *",
            ],
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(name="hello/test")

        assert deployment.schedule.cron == "* * * * *"

    async def test_flow_serve_cli_accepts_rrule(
        self, prefect_client: PrefectClient, mock_runner_start
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow",
                "serve",
                "flows/hello_world.py:hello",
                "--name",
                "test",
                "--rrule",
                "FREQ=MINUTELY;COUNT=5",
            ],
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(name="hello/test")

        assert deployment.schedule.rrule == "FREQ=MINUTELY;COUNT=5"

    async def test_flow_serve_cli_accepts_metadata_fields(
        self, prefect_client: PrefectClient, mock_runner_start
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow",
                "serve",
                "flows/hello_world.py:hello",
                "--name",
                "test",
                "--description",
                "test description",
                "--tag",
                "test",
                "--tag",
                "test2",
                "--version",
                "1.0.0",
            ],
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(name="hello/test")

        assert deployment.description == "test description"
        assert deployment.tags == ["test", "test2"]
        assert deployment.version == "1.0.0"
