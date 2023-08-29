import datetime
from pathlib import Path
from time import sleep

import anyio
import pytest

from prefect import flow, serve
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import StateType
from prefect.deployments.runner import RunnerDeployment
from prefect.runner import Runner


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


class TestServe:
    async def test_serve_can_create_multiple_deployments(
        self,
        prefect_client: PrefectClient,
    ):
        async with anyio.create_task_group() as tg:
            with anyio.CancelScope(shield=True):
                deployment_1 = dummy_flow_1.to_deployment(__file__, interval=3600)
                deployment_2 = dummy_flow_2.to_deployment(__file__, cron="* * * * *")

                tg.start_soon(serve, deployment_1, deployment_2)

                await anyio.sleep(1)
                tg.cancel_scope.cancel()

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

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_serve_can_cancel_flow_runs(self, prefect_client: PrefectClient):
        async with anyio.create_task_group() as tg:
            deployment = tired_flow.to_deployment("test")

            tg.start_soon(serve, deployment)

            await anyio.sleep(1)

            deployment = await prefect_client.read_deployment_by_name(
                name="tired-flow/test"
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
                if flow_run.state.is_final():
                    break

            tg.cancel_scope.cancel()

        assert flow_run.state.is_cancelled()

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_serve_can_execute_scheduled_flow_runs(
        self, prefect_client: PrefectClient
    ):
        async with anyio.create_task_group() as tg:
            deployment = dummy_flow_1.to_deployment("test")

            tg.start_soon(serve, deployment)

            await anyio.sleep(1)

            deployment = await prefect_client.read_deployment_by_name(
                name="dummy-flow-1/test"
            )

            flow_run = await prefect_client.create_flow_run_from_deployment(
                deployment_id=deployment.id
            )
            # Need to wait for polling loop to pick up flow run and then
            # finish execution
            for _ in range(15):
                await anyio.sleep(1)
                flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
                if flow_run.state.is_final():
                    break

            tg.cancel_scope.cancel()

        assert flow_run.state.is_completed()


class TestRunner:
    async def test_add_flows_to_runner(self, prefect_client: PrefectClient):
        """Runner.add should create a deployment for the flow passed to it"""
        runner = Runner()

        deployment_id_1 = await runner.add(dummy_flow_1, __file__, interval=3600)
        deployment_id_2 = await runner.add(dummy_flow_2, __file__, cron="* * * * *")

        deployment_1 = await prefect_client.read_deployment(deployment_id_1)
        deployment_2 = await prefect_client.read_deployment(deployment_id_2)

        assert deployment_1 is not None
        assert deployment_1.name == "test_runner"
        assert deployment_1.schedule.interval == datetime.timedelta(seconds=3600)

        assert deployment_2 is not None
        assert deployment_2.name == "test_runner"
        assert deployment_2.schedule.cron == "* * * * *"

    async def test_add_fails_with_multiple_schedules(self):
        runner = Runner()

        with pytest.raises(
            ValueError, match="Only one of interval, cron, or rrule can be provided."
        ):
            await runner.add(dummy_flow_1, name="test", interval=3600, cron="* * * * *")

        with pytest.raises(
            ValueError, match="Only one of interval, cron, or rrule can be provided."
        ):
            await runner.add(
                dummy_flow_1, name="test", interval=3600, rrule="FREQ=MINUTELY"
            )

        with pytest.raises(
            ValueError, match="Only one of interval, cron, or rrule can be provided."
        ):
            await runner.add(
                dummy_flow_1, name="test", cron="* * * * *", rrule="FREQ=MINUTELY"
            )

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
        self, prefect_client: PrefectClient
    ):
        runner = Runner()

        deployment_1 = dummy_flow_1.to_deployment(__file__, interval=3600)
        deployment_2 = dummy_flow_2.to_deployment(__file__, cron="* * * * *")

        await runner.add_deployment(deployment_1)
        await runner.add_deployment(deployment_2)

        async with anyio.create_task_group() as tg:
            tg.start_soon(runner.start)

            deployment_1 = await prefect_client.read_deployment_by_name(
                name="dummy-flow-1/test_runner"
            )
            deployment_2 = await prefect_client.read_deployment_by_name(
                name="dummy-flow-2/test_runner"
            )

            assert deployment_1.is_schedule_active

            assert deployment_2.is_schedule_active

            runner.stop()

        deployment_1 = await prefect_client.read_deployment_by_name(
            name="dummy-flow-1/test_runner"
        )
        deployment_2 = await prefect_client.read_deployment_by_name(
            name="dummy-flow-2/test_runner"
        )

        assert not deployment_1.is_schedule_active

        assert not deployment_2.is_schedule_active

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_executes_flow_runs(self, prefect_client: PrefectClient):
        runner = Runner(query_seconds=2)

        deployment = dummy_flow_1.to_deployment(__file__)

        await runner.add_deployment(deployment)

        async with anyio.create_task_group() as tg:
            tg.start_soon(runner.start)

            deployment = await prefect_client.read_deployment_by_name(
                name="dummy-flow-1/test_runner"
            )

            flow_run = await prefect_client.create_flow_run_from_deployment(
                deployment_id=deployment.id
            )

            # Need to wait for polling loop to pick up flow run and then
            # finish execution
            for _ in range(15):
                await anyio.sleep(1)
                flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
                if flow_run.state.is_final():
                    break

            runner.stop()

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


class TestDeploymentRunner:
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
        )

        assert deployment.name == "test_runner"
        assert deployment.flow_name == "dummy-flow-1"
        assert deployment.entrypoint == f"{relative_file_path}:dummy_flow_1"
        assert deployment.description == "Deployment descriptions"
        assert deployment.version == "alpha"
        assert deployment.tags == ["test"]

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

    def test_from_flow_raises_on_multiple_schedules(self):
        with pytest.raises(
            ValueError, match="Only one of interval, cron, or rrule can be provided."
        ):
            RunnerDeployment.from_flow(
                dummy_flow_1, __file__, interval=3600, cron="* * * * *"
            )

        with pytest.raises(
            ValueError, match="Only one of interval, cron, or rrule can be provided."
        ):
            RunnerDeployment.from_flow(
                dummy_flow_1, __file__, interval=3600, rrule="FREQ=MINUTELY"
            )

        with pytest.raises(
            ValueError, match="Only one of interval, cron, or rrule can be provided."
        ):
            RunnerDeployment.from_flow(
                dummy_flow_1, __file__, cron="* * * * *", rrule="FREQ=MINUTELY"
            )

    def test_from_flow_uses_defaults_from_flow(self):
        deployment = RunnerDeployment.from_flow(dummy_flow_1, __file__)

        assert deployment.version == "test"
        assert deployment.description == "I'm just here for tests"

    def test_from_entrypoint(self, dummy_flow_1_entrypoint):
        deployment = RunnerDeployment.from_entrypoint(
            dummy_flow_1_entrypoint,
            __file__,
            tags=["test"],
            version="alpha",
            description="Deployment descriptions",
        )

        assert deployment.name == "test_runner"
        assert deployment.flow_name == "dummy-flow-1"
        assert deployment.entrypoint == "tests/test_runner.py:dummy_flow_1"
        assert deployment.description == "Deployment descriptions"
        assert deployment.version == "alpha"
        assert deployment.tags == ["test"]

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

    def test_from_entrypoint_raises_on_multiple_schedules(
        self, dummy_flow_1_entrypoint
    ):
        with pytest.raises(
            ValueError, match="Only one of interval, cron, or rrule can be provided."
        ):
            RunnerDeployment.from_entrypoint(
                dummy_flow_1_entrypoint, __file__, interval=3600, cron="* * * * *"
            )

        with pytest.raises(
            ValueError, match="Only one of interval, cron, or rrule can be provided."
        ):
            RunnerDeployment.from_entrypoint(
                dummy_flow_1_entrypoint, __file__, interval=3600, rrule="FREQ=MINUTELY"
            )

        with pytest.raises(
            ValueError, match="Only one of interval, cron, or rrule can be provided."
        ):
            RunnerDeployment.from_entrypoint(
                dummy_flow_1_entrypoint,
                __file__,
                cron="* * * * *",
                rrule="FREQ=MINUTELY",
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
