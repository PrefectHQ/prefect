import datetime
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from prefect import __development_base_path__, flow
from prefect.client.orchestration import PrefectClient
from prefect.runner import Runner
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread


@flow(retries=2)
def hello():
    print("hello")


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
        deployment_name = f"test-{uuid.uuid4()}"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow",
                "serve",
                f"{__development_base_path__}/tests/cli/test_flow.py:hello",
                "--name",
                deployment_name,
            ],
            expected_code=0,
            expected_output_contains=[
                "Your flow 'hello' is being served and polling for scheduled runs!",
                "To trigger a run for this flow, use the following command",
                f"$ prefect deployment run 'hello/{deployment_name}'",
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            name=f"hello/{deployment_name}"
        )

        assert deployment is not None
        assert deployment.name == deployment_name
        assert (
            deployment.entrypoint
            == f"{__development_base_path__}/tests/cli/test_flow.py:hello"
        )

        mock_runner_start.assert_called_once()

    async def test_flow_serve_cli_accepts_interval(
        self, prefect_client: PrefectClient, mock_runner_start
    ):
        deployment_name = f"test-{uuid.uuid4()}"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow",
                "serve",
                f"{__development_base_path__}/tests/cli/test_flow.py:hello",
                "--name",
                deployment_name,
                "--interval",
                "3600",
            ],
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(
            name=f"hello/{deployment_name}"
        )

        assert len(deployment.schedules) == 1
        schedule = deployment.schedules[0].schedule
        assert schedule.interval == datetime.timedelta(seconds=3600)

    async def test_flow_serve_cli_accepts_cron(
        self, prefect_client: PrefectClient, mock_runner_start
    ):
        deployment_name = f"test-{uuid.uuid4()}"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow",
                "serve",
                f"{__development_base_path__}/tests/cli/test_flow.py:hello",
                "--name",
                deployment_name,
                "--cron",
                "* * * * *",
            ],
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(
            name=f"hello/{deployment_name}"
        )
        assert len(deployment.schedules) == 1
        assert deployment.schedules[0].schedule.cron == "* * * * *"

    async def test_flow_serve_cli_accepts_rrule(
        self, prefect_client: PrefectClient, mock_runner_start
    ):
        deployment_name = f"test-{uuid.uuid4()}"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow",
                "serve",
                f"{__development_base_path__}/tests/cli/test_flow.py:hello",
                "--name",
                deployment_name,
                "--rrule",
                "FREQ=MINUTELY;COUNT=5",
            ],
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(
            name=f"hello/{deployment_name}"
        )
        assert len(deployment.schedules) == 1
        assert deployment.schedules[0].schedule.rrule == "FREQ=MINUTELY;COUNT=5"

    async def test_flow_serve_cli_accepts_limit(
        self,
        prefect_client: PrefectClient,
        mock_runner_start,
        monkeypatch: pytest.MonkeyPatch,
    ):
        runner_init_args: dict[str, Any] = {}

        original_runner_init = Runner.__init__

        def runner_spy_init(self: Runner, *args: Any, **kwargs: Any):
            runner_init_args.update(kwargs)
            return original_runner_init(self, *args, **kwargs)

        monkeypatch.setattr(Runner, "__init__", runner_spy_init)

        deployment_name = f"test-{uuid.uuid4()}"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow",
                "serve",
                f"{__development_base_path__}/tests/cli/test_flow.py:hello",
                "--name",
                deployment_name,
                "--limit",
                "5",
                "--global-limit",
                "13",
            ],
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(
            name=f"hello/{deployment_name}"
        )
        assert deployment.global_concurrency_limit is not None
        assert deployment.global_concurrency_limit.limit == 13
        assert runner_init_args["limit"] == 5

    async def test_flow_serve_cli_accepts_metadata_fields(
        self, prefect_client: PrefectClient, mock_runner_start
    ):
        deployment_name = f"test-{uuid.uuid4()}"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow",
                "serve",
                f"{__development_base_path__}/tests/cli/test_flow.py:hello",
                "--name",
                deployment_name,
                "--description",
                "test description",
                "--tag",
                "test-tag",
                "--tag",
                "test-tag2",
                "--version",
                "1.0.0",
            ],
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(
            name=f"hello/{deployment_name}"
        )

        assert deployment.description == "test description"
        assert deployment.tags == ["test-tag", "test-tag2"]
        assert deployment.version == "1.0.0"
