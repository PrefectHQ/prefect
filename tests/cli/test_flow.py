import datetime
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

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
        monkeypatch.setattr(Runner, "start", mock)
        return mock

    def test_flow_serve_cli_requires_entrypoint(self):
        is_fast = os.environ.get("PREFECT_CLI_FAST", "").lower() in ("1", "true")
        invoke_and_assert(
            command=["flow", "serve"],
            expected_code=1 if is_fast else 2,
            expected_output_contains=(
                "requires an argument" if is_fast else "Missing argument 'ENTRYPOINT'."
            ),
        )

    async def test_flow_serve_cli_creates_deployment(
        self, prefect_client: PrefectClient, mock_runner_start: AsyncMock
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow",
                "serve",
                f"{__development_base_path__}/tests/cli/test_flow.py:hello",
                "--name",
                "test",
            ],
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
        assert (
            deployment.entrypoint
            == f"{__development_base_path__}/tests/cli/test_flow.py:hello"
        )

        mock_runner_start.assert_called_once()

    async def test_flow_serve_cli_accepts_interval(
        self, prefect_client: PrefectClient, mock_runner_start
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow",
                "serve",
                f"{__development_base_path__}/tests/cli/test_flow.py:hello",
                "--name",
                "test",
                "--interval",
                "3600",
            ],
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(name="hello/test")

        assert len(deployment.schedules) == 1
        schedule = deployment.schedules[0].schedule
        assert schedule.interval == datetime.timedelta(seconds=3600)

    async def test_flow_serve_cli_accepts_cron(
        self, prefect_client: PrefectClient, mock_runner_start
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow",
                "serve",
                f"{__development_base_path__}/tests/cli/test_flow.py:hello",
                "--name",
                "test",
                "--cron",
                "* * * * *",
            ],
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(name="hello/test")
        assert len(deployment.schedules) == 1
        assert deployment.schedules[0].schedule.cron == "* * * * *"

    async def test_flow_serve_cli_accepts_rrule(
        self, prefect_client: PrefectClient, mock_runner_start
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow",
                "serve",
                f"{__development_base_path__}/tests/cli/test_flow.py:hello",
                "--name",
                "test",
                "--rrule",
                "FREQ=MINUTELY;COUNT=5",
            ],
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(name="hello/test")
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

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow",
                "serve",
                f"{__development_base_path__}/tests/cli/test_flow.py:hello",
                "--name",
                "test",
                "--limit",
                "5",
                "--global-limit",
                "13",
            ],
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(name="hello/test")
        assert deployment.global_concurrency_limit is not None
        assert deployment.global_concurrency_limit.limit == 13
        assert runner_init_args["limit"] == 5

    async def test_flow_serve_cli_accepts_metadata_fields(
        self, prefect_client: PrefectClient, mock_runner_start
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow",
                "serve",
                f"{__development_base_path__}/tests/cli/test_flow.py:hello",
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


class TestFlowLs:
    """Tests for the `prefect flow ls` command."""

    async def test_ls_no_output_flag(self, prefect_client):
        """Test flow ls without output flag renders a Rich table."""
        @flow(name="test-flow-ls")
        def my_flow():
            pass

        await prefect_client.create_flow(my_flow)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=["flow", "ls"],
            expected_code=0,
            expected_output_contains="Flows",
        )

    async def test_ls_json_output(self, prefect_client):
        """Test flow ls with --output json returns valid JSON array."""
        import json

        @flow(name="test-flow-ls-json")
        def my_flow():
            pass

        created = await prefect_client.create_flow(my_flow)

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=["flow", "ls", "--output", "json"],
            expected_code=0,
        )

        output_data = json.loads(result.stdout.strip())
        assert isinstance(output_data, list)
        assert len(output_data) >= 1
        # Find our flow in the output
        flow_data = next((f for f in output_data if f["id"] == str(created.id)), None)
        assert flow_data is not None
        assert flow_data["name"] == "test-flow-ls-json"

    async def test_ls_json_output_short_flag(self, prefect_client):
        """Test flow ls with -o json returns valid JSON array."""
        import json

        @flow(name="test-flow-ls-json-short")
        def my_flow():
            pass

        created = await prefect_client.create_flow(my_flow)

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=["flow", "ls", "-o", "json"],
            expected_code=0,
        )

        output_data = json.loads(result.stdout.strip())
        assert isinstance(output_data, list)
        # Find our flow in the output
        flow_data = next((f for f in output_data if f["id"] == str(created.id)), None)
        assert flow_data is not None
        assert flow_data["name"] == "test-flow-ls-json-short"

    def test_ls_json_output_empty(self):
        """Test flow ls with --output json when no flows exist returns empty list."""
        import json
        from prefect.client.orchestration import get_client

        # Mock get_client to return a mock context manager
        mock_client = AsyncMock()
        mock_client.read_flows.return_value = []
        
        mock_get_client_ctx = AsyncMock()
        mock_get_client_ctx.__aenter__.return_value = mock_client
        mock_get_client_ctx.__aexit__.return_value = None
        
        with pytest.MonkeyPatch.context() as m:
            m.setattr("prefect.cli.flow.get_client", MagicMock(return_value=mock_get_client_ctx))
            
            result = invoke_and_assert(
                command=["flow", "ls", "-o", "json"],
                expected_code=0,
            )

            output_data = json.loads(result.stdout.strip())
            assert output_data == []

    def test_ls_invalid_output_format(self):
        """Test flow ls with unsupported output format exits with error."""
        invoke_and_assert(
            command=["flow", "ls", "-o", "xml"],
            expected_code=1,
            expected_output_contains="Only 'json' output format is supported.",
        )
