import datetime
from itertools import combinations
from pathlib import Path
from time import sleep

import anyio
import pytest

from prefect import flow, serve
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import StateType
from prefect.client.schemas.schedules import CronSchedule
from prefect.deployments.runner import RunnerDeployment
from prefect.flows import load_flow_from_entrypoint
from prefect.runner import Runner
from prefect.settings import PREFECT_RUNNER_PROCESS_LIMIT, temporary_settings
from prefect.testing.utilities import AsyncMock


@flow(version="test")
def dummy_flow_1():
    """I'm just here for tests"""
    pass


@flow
def dummy_flow_2():
    pass


@flow()
def tired_flow():
    print("I am so tired...")

    for _ in range(100):
        print("zzzzz...")
        sleep(5)


class TestInit:
    async def test_runner_respects_limit_setting(self):
        runner = Runner()
        assert runner.limit == PREFECT_RUNNER_PROCESS_LIMIT.value()

        runner = Runner(limit=50)
        assert runner.limit == 50

        with temporary_settings({PREFECT_RUNNER_PROCESS_LIMIT: 100}):
            runner = Runner()
            assert runner.limit == 100


class TestServe:
    @pytest.fixture(autouse=True)
    async def mock_runner_start(self, monkeypatch):
        mock = AsyncMock()
        monkeypatch.setattr("prefect.runner.Runner.start", mock)
        return mock

    async def test_serve_prints_help_message_on_startup(self, capsys):
        await serve(
            dummy_flow_1.to_deployment(__file__),
            dummy_flow_2.to_deployment(__file__),
            tired_flow.to_deployment(__file__),
        )

        captured = capsys.readouterr()

        assert (
            "Your deployments are being served and polling for scheduled runs!"
            in captured.out
        )
        assert "dummy-flow-1/test_runner" in captured.out
        assert "dummy-flow-2/test_runner" in captured.out
        assert "tired-flow/test_runner" in captured.out
        assert "$ prefect deployment run [DEPLOYMENT_NAME]" in captured.out

    async def test_serve_can_create_multiple_deployments(
        self,
        prefect_client: PrefectClient,
    ):
        deployment_1 = dummy_flow_1.to_deployment(__file__, interval=3600)
        deployment_2 = dummy_flow_2.to_deployment(__file__, cron="* * * * *")

        await serve(deployment_1, deployment_2)

        deployment = await prefect_client.read_deployment_by_name(
            name="dummy-flow-1/test_runner"
        )

        assert deployment is not None
        assert deployment.schedule.interval == datetime.timedelta(seconds=3600)

        deployment = await prefect_client.read_deployment_by_name(
            name="dummy-flow-2/test_runner"
        )

        assert deployment is not None
        assert deployment.schedule.cron == "* * * * *"

    async def test_serve_starts_a_runner(
        self, prefect_client: PrefectClient, mock_runner_start: AsyncMock
    ):
        deployment = dummy_flow_1.to_deployment("test")

        await serve(deployment)

        mock_runner_start.assert_awaited_once()


class TestRunner:
    async def test_add_flows_to_runner(self, prefect_client: PrefectClient):
        """Runner.add should create a deployment for the flow passed to it"""
        runner = Runner()

        deployment_id_1 = await runner.add_flow(dummy_flow_1, __file__, interval=3600)
        deployment_id_2 = await runner.add_flow(
            dummy_flow_2, __file__, cron="* * * * *"
        )

        deployment_1 = await prefect_client.read_deployment(deployment_id_1)
        deployment_2 = await prefect_client.read_deployment(deployment_id_2)

        assert deployment_1 is not None
        assert deployment_1.name == "test_runner"
        assert deployment_1.schedule.interval == datetime.timedelta(seconds=3600)

        assert deployment_2 is not None
        assert deployment_2.name == "test_runner"
        assert deployment_2.schedule.cron == "* * * * *"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {**d1, **d2}
            for d1, d2 in combinations(
                [
                    {"interval": 3600},
                    {"cron": "* * * * *"},
                    {"rrule": "FREQ=MINUTELY"},
                    {"schedule": CronSchedule(cron="* * * * *")},
                ],
                2,
            )
        ],
    )
    async def test_add_flow_raises_on_multiple_schedules(self, kwargs):
        expected_message = (
            "Only one of interval, cron, rrule, or schedule can be provided."
        )
        runner = Runner()
        with pytest.raises(ValueError, match=expected_message):
            await runner.add_flow(dummy_flow_1, __file__, **kwargs)

    async def test_add_deployments_to_runner(self, prefect_client: PrefectClient):
        """Runner.add_deployment should apply the deployment passed to it"""
        runner = Runner()

        deployment_1 = dummy_flow_1.to_deployment(__file__, interval=3600)
        deployment_2 = dummy_flow_2.to_deployment(__file__, cron="* * * * *")

        deployment_id_1 = await runner.add_deployment(deployment_1)
        deployment_id_2 = await runner.add_deployment(deployment_2)

        deployment_1 = await prefect_client.read_deployment(deployment_id_1)
        deployment_2 = await prefect_client.read_deployment(deployment_id_2)

        assert deployment_1 is not None
        assert deployment_1.name == "test_runner"
        assert deployment_1.schedule.interval == datetime.timedelta(seconds=3600)

        assert deployment_2 is not None
        assert deployment_2.name == "test_runner"
        assert deployment_2.schedule.cron == "* * * * *"

    async def test_runner_can_pause_schedules_on_stop(
        self, prefect_client: PrefectClient, caplog
    ):
        runner = Runner()

        deployment_1 = dummy_flow_1.to_deployment(__file__, interval=3600)
        deployment_2 = dummy_flow_2.to_deployment(__file__, cron="* * * * *")

        await runner.add_deployment(deployment_1)
        await runner.add_deployment(deployment_2)

        deployment_1 = await prefect_client.read_deployment_by_name(
            name="dummy-flow-1/test_runner"
        )
        deployment_2 = await prefect_client.read_deployment_by_name(
            name="dummy-flow-2/test_runner"
        )

        assert deployment_1.is_schedule_active

        assert deployment_2.is_schedule_active

        await runner.start(run_once=True)

        deployment_1 = await prefect_client.read_deployment_by_name(
            name="dummy-flow-1/test_runner"
        )
        deployment_2 = await prefect_client.read_deployment_by_name(
            name="dummy-flow-2/test_runner"
        )

        assert not deployment_1.is_schedule_active

        assert not deployment_2.is_schedule_active

        assert "Pausing schedules for all deployments" in caplog.text
        assert "All deployment schedules have been paused" in caplog.text

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_executes_flow_runs(self, prefect_client: PrefectClient):
        runner = Runner()

        deployment = dummy_flow_1.to_deployment(__file__)

        await runner.add_deployment(deployment)

        await runner.start(run_once=True)

        deployment = await prefect_client.read_deployment_by_name(
            name="dummy-flow-1/test_runner"
        )

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment.id
        )

        await runner.start(run_once=True)
        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)

        assert flow_run.state.is_completed()

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_can_cancel_flow_runs(self, prefect_client: PrefectClient):
        runner = Runner(query_seconds=2)

        deployment = tired_flow.to_deployment(__file__)

        await runner.add_deployment(deployment)

        async with anyio.create_task_group() as tg:
            tg.start_soon(runner.start)

            deployment = await prefect_client.read_deployment_by_name(
                name="tired-flow/test_runner"
            )

            flow_run = await prefect_client.create_flow_run_from_deployment(
                deployment_id=deployment.id
            )

            # Need to wait for polling loop to pick up flow run and
            # start execution
            for _ in range(15):
                await anyio.sleep(1)
                flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
                if flow_run.state.is_running():
                    break

            await prefect_client.set_flow_run_state(
                flow_run_id=flow_run.id,
                state=flow_run.state.copy(
                    update={"name": "Cancelled", "type": StateType.CANCELLED}
                ),
            )

            # Need to wait for polling loop to pick up flow run and then
            # finish cancellation
            for _ in range(15):
                await anyio.sleep(1)
                flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
                if flow_run.state.is_cancelled():
                    break

            runner.stop()
            tg.cancel_scope.cancel()

        assert flow_run.state.is_cancelled()

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_can_execute_a_single_flow_run(
        self, prefect_client: PrefectClient
    ):
        runner = Runner()

        deployment_id = await dummy_flow_1.to_deployment(__file__).apply()

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )
        await runner.execute_flow_run(flow_run.id)

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert flow_run.state.is_completed()

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_respects_set_limit(
        self, prefect_client: PrefectClient, caplog
    ):
        runner = Runner(limit=1)

        deployment_id = await dummy_flow_1.to_deployment(__file__).apply()

        good_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )
        bad_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )
        runner._acquire_limit_slot(good_run.id)
        await runner.execute_flow_run(bad_run.id)
        assert "run limit reached" in caplog.text

        flow_run = await prefect_client.read_flow_run(flow_run_id=bad_run.id)
        assert flow_run.state.is_scheduled()

        runner._release_limit_slot(good_run.id)
        await runner.execute_flow_run(bad_run.id)

        flow_run = await prefect_client.read_flow_run(flow_run_id=bad_run.id)
        assert flow_run.state.is_completed()


class TestRunnerDeployment:
    @pytest.fixture
    def relative_file_path(self):
        return Path(__file__).relative_to(Path.cwd())

    @pytest.fixture
    def dummy_flow_1_entrypoint(self, relative_file_path):
        return f"{relative_file_path}:dummy_flow_1"

    def test_from_flow(self, relative_file_path):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1,
            __file__,
            tags=["test"],
            version="alpha",
            description="Deployment descriptions",
            enforce_parameter_schema=True,
        )

        assert deployment.name == "test_runner"
        assert deployment.flow_name == "dummy-flow-1"
        assert deployment.entrypoint == f"{relative_file_path}:dummy_flow_1"
        assert deployment.description == "Deployment descriptions"
        assert deployment.version == "alpha"
        assert deployment.tags == ["test"]
        assert deployment.enforce_parameter_schema

    def test_from_flow_accepts_interval(self):
        deployment = RunnerDeployment.from_flow(dummy_flow_1, __file__, interval=3600)

        assert deployment.schedule.interval == datetime.timedelta(seconds=3600)

    def test_from_flow_accepts_cron(self):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1, __file__, cron="* * * * *"
        )

        assert deployment.schedule.cron == "* * * * *"

    def test_from_flow_accepts_rrule(self):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1, __file__, rrule="FREQ=MINUTELY"
        )

        assert deployment.schedule.rrule == "FREQ=MINUTELY"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {**d1, **d2}
            for d1, d2 in combinations(
                [
                    {"interval": 3600},
                    {"cron": "* * * * *"},
                    {"rrule": "FREQ=MINUTELY"},
                    {"schedule": CronSchedule(cron="* * * * *")},
                ],
                2,
            )
        ],
    )
    def test_from_flow_raises_on_multiple_schedules(self, kwargs):
        expected_message = (
            "Only one of interval, cron, rrule, or schedule can be provided."
        )
        with pytest.raises(ValueError, match=expected_message):
            RunnerDeployment.from_flow(dummy_flow_1, __file__, **kwargs)

    def test_from_flow_uses_defaults_from_flow(self):
        deployment = RunnerDeployment.from_flow(dummy_flow_1, __file__)

        assert deployment.version == "test"
        assert deployment.description == "I'm just here for tests"

    def test_from_flow_raises_when_using_flow_loaded_from_entrypoint(self):
        da_flow = load_flow_from_entrypoint("tests/test_runner.py:dummy_flow_1")

        with pytest.raises(
            ValueError,
            match=(
                "Cannot create a RunnerDeployment from a flow that has been loaded from"
                " an entrypoint"
            ),
        ):
            RunnerDeployment.from_flow(da_flow, __file__)

    def test_from_flow_raises_on_interactively_defined_flow(self):
        @flow
        def da_flow():
            pass

        # Clear __module__ to test it's handled correctly
        da_flow.__module__ = None

        with pytest.raises(
            ValueError,
            match="Flows defined interactively cannot be deployed.",
        ):
            RunnerDeployment.from_flow(da_flow, __file__)

        # muck up __module__ so that it looks like it was defined interactively
        da_flow.__module__ = "__main__"

        with pytest.raises(
            ValueError,
            match="Flows defined interactively cannot be deployed.",
        ):
            RunnerDeployment.from_flow(da_flow, __file__)

    def test_from_entrypoint(self, dummy_flow_1_entrypoint):
        deployment = RunnerDeployment.from_entrypoint(
            dummy_flow_1_entrypoint,
            __file__,
            tags=["test"],
            version="alpha",
            description="Deployment descriptions",
            enforce_parameter_schema=True,
        )

        assert deployment.name == "test_runner"
        assert deployment.flow_name == "dummy-flow-1"
        assert deployment.entrypoint == "tests/test_runner.py:dummy_flow_1"
        assert deployment.description == "Deployment descriptions"
        assert deployment.version == "alpha"
        assert deployment.tags == ["test"]
        assert deployment.enforce_parameter_schema

    def test_from_entrypoint_accepts_interval(self, dummy_flow_1_entrypoint):
        deployment = RunnerDeployment.from_entrypoint(
            dummy_flow_1_entrypoint, __file__, interval=3600
        )

        assert deployment.schedule.interval == datetime.timedelta(seconds=3600)

    def test_from_entrypoint_accepts_cron(self, dummy_flow_1_entrypoint):
        deployment = RunnerDeployment.from_entrypoint(
            dummy_flow_1_entrypoint, __file__, cron="* * * * *"
        )

        assert deployment.schedule.cron == "* * * * *"

    def test_from_entrypoint_accepts_rrule(self, dummy_flow_1_entrypoint):
        deployment = RunnerDeployment.from_entrypoint(
            dummy_flow_1_entrypoint, __file__, rrule="FREQ=MINUTELY"
        )

        assert deployment.schedule.rrule == "FREQ=MINUTELY"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {**d1, **d2}
            for d1, d2 in combinations(
                [
                    {"interval": 3600},
                    {"cron": "* * * * *"},
                    {"rrule": "FREQ=MINUTELY"},
                    {"schedule": CronSchedule(cron="* * * * *")},
                ],
                2,
            )
        ],
    )
    def test_from_entrypoint_raises_on_multiple_schedules(
        self, dummy_flow_1_entrypoint, kwargs
    ):
        expected_message = (
            "Only one of interval, cron, rrule, or schedule can be provided."
        )
        with pytest.raises(ValueError, match=expected_message):
            RunnerDeployment.from_entrypoint(
                dummy_flow_1_entrypoint, __file__, **kwargs
            )

    def test_from_entrypoint_uses_defaults_from_entrypoint(
        self, dummy_flow_1_entrypoint
    ):
        deployment = RunnerDeployment.from_entrypoint(dummy_flow_1_entrypoint, __file__)

        assert deployment.version == "test"
        assert deployment.description == "I'm just here for tests"

    async def test_apply(self, prefect_client: PrefectClient):
        deployment = RunnerDeployment.from_flow(dummy_flow_1, __file__, interval=3600)

        deployment_id = await deployment.apply()

        deployment = await prefect_client.read_deployment(deployment_id)

        assert deployment.name == "test_runner"
        assert deployment.entrypoint == "tests/test_runner.py:dummy_flow_1"
        assert deployment.version == "test"
        assert deployment.description == "I'm just here for tests"
        assert deployment.schedule.interval == datetime.timedelta(seconds=3600)
        assert deployment.work_pool_name is None
        assert deployment.work_queue_name is None
        assert deployment.path == str(Path.cwd())
        assert deployment.enforce_parameter_schema is False
