from __future__ import annotations

import asyncio
import datetime
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import uuid
import warnings
from itertools import combinations
from pathlib import Path
from textwrap import dedent
from time import sleep
from typing import TYPE_CHECKING, Any, Coroutine, Generator, List, Union
from unittest import mock
from unittest.mock import MagicMock, patch

import anyio
import pytest
import uv
from starlette import status

import prefect.runner
from prefect import __version__, aserve, flow, serve, task
from prefect._experimental.bundles import create_bundle_for_flow_run
from prefect._internal.compatibility.deprecated import PrefectDeprecationWarning
from prefect._versioning import VersionType
from prefect.cli.deploy._storage import _PullStepStorage
from prefect.client.orchestration import PrefectClient, SyncPrefectClient
from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.objects import (
    ConcurrencyLimitConfig,
    FlowRun,
    State,
    StateType,
    VersionInfo,
    Worker,
    WorkerStatus,
)
from prefect.client.schemas.schedules import CronSchedule, IntervalSchedule
from prefect.deployments.runner import (
    DeploymentApplyError,
    EntrypointType,
    RunnerDeployment,
    deploy,
)
from prefect.docker.docker_image import DockerImage
from prefect.events.clients import (
    AssertingEventsClient,
)
from prefect.events.schemas.automations import Posture
from prefect.events.schemas.deployment_triggers import DeploymentEventTrigger
from prefect.events.schemas.events import Event
from prefect.exceptions import ScriptError
from prefect.flows import Flow
from prefect.logging.loggers import flow_run_logger
from prefect.runner.runner import Runner
from prefect.runner.server import perform_health_check, start_webserver
from prefect.schedules import Cron, Interval
from prefect.settings import (
    PREFECT_DEFAULT_DOCKER_BUILD_NAMESPACE,
    PREFECT_DEFAULT_WORK_POOL_NAME,
    PREFECT_RUNNER_HEARTBEAT_FREQUENCY,
    PREFECT_RUNNER_POLL_FREQUENCY,
    PREFECT_RUNNER_PROCESS_LIMIT,
    PREFECT_RUNNER_SERVER_ENABLE,
    temporary_settings,
)
from prefect.states import Cancelling, Crashed
from prefect.testing.utilities import AsyncMock
from prefect.types._datetime import now
from prefect.utilities import processutils
from prefect.utilities.annotations import freeze
from prefect.utilities.dockerutils import parse_image_tag
from prefect.utilities.filesystem import tmpchdir
from prefect.utilities.slugify import slugify


@pytest.fixture(autouse=True)
def suppress_deprecation_warnings() -> Generator[None, None, None]:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PrefectDeprecationWarning)
        yield


@flow(version="test")
def dummy_flow_1():
    """I'm just here for tests"""
    pass


@flow
def dummy_flow_2():
    pass


class ClassNameStaticmethod:
    @flow
    @staticmethod
    def dummy_flow_staticmethod():
        pass


class ClassNameClassmethod:
    @flow
    @classmethod
    def dummy_flow_classmethod(cls):
        pass


@task
def my_task(seconds: int):
    time.sleep(seconds)


def on_cancellation(flow, flow_run, state):
    logger = flow_run_logger(flow_run, flow)
    logger.info("This flow was cancelled!")


@flow(on_cancellation=[on_cancellation], log_prints=True)
def cancel_flow_submitted_tasks(sleep_time: int = 100):
    my_task.submit(sleep_time)


def on_crashed(flow, flow_run, state):
    logger = flow_run_logger(flow_run, flow)
    logger.info("This flow crashed!")


@flow(on_crashed=[on_crashed], log_prints=True)
def crashing_flow():
    print("Oh boy, here I go crashing again...")
    os.kill(os.getpid(), signal.SIGTERM)


@flow()
def tired_flow():
    print("I am so tired...")

    for _ in range(100):
        print("zzzzz...")
        sleep(5)


@flow
def short_but_not_too_short():
    time.sleep(5)


@pytest.fixture
def patch_run_process(monkeypatch: pytest.MonkeyPatch):
    def patch_run_process(returncode: int = 0, pid: int = 1000):
        mock_run_process = AsyncMock()
        mock_process = MagicMock()
        mock_process.returncode = returncode
        mock_process.pid = pid
        mock_run_process.return_value = mock_process

        async def side_effect(
            *args: Any,
            **kwargs: Any,
        ):
            kwargs["task_status"].started(mock_process)
            return MagicMock(returncode=returncode, pid=pid)

        mock_run_process.side_effect = side_effect

        monkeypatch.setattr(prefect.runner.runner, "run_process", mock_run_process)

        return mock_run_process

    return patch_run_process


@pytest.fixture
def mock_events_client(monkeypatch: pytest.MonkeyPatch):
    mock_events_client = AssertingEventsClient()
    monkeypatch.setattr(
        "prefect.runner.runner.get_events_client",
        lambda *args, **kwargs: mock_events_client,
    )
    yield mock_events_client

    AssertingEventsClient.reset()


class MockStorage:
    """
    A mock storage class that simulates pulling code from a remote location.
    """

    def __init__(self, base_path: Path, pull_code_spy: Union[MagicMock, None] = None):
        self._base_path = base_path
        self._pull_code_spy = pull_code_spy

    def set_base_path(self, path: Path):
        self._base_path = path

    code = dedent(
        """\
        from prefect import flow

        @flow
        def test_flow():
            return 1
        """
    )

    @property
    def destination(self):
        return self._base_path

    @property
    def pull_interval(self):
        return 60

    async def pull_code(self):
        if self._pull_code_spy:
            self._pull_code_spy()

        if self._base_path:
            with open(self._base_path / "flows.py", "w") as f:
                f.write(self.code)

    def to_pull_step(self):
        return {"prefect.fake.module": {}}


@pytest.fixture
def temp_storage() -> Generator[MockStorage, Any, None]:
    with tempfile.TemporaryDirectory() as temp_dir:
        yield MockStorage(base_path=Path(temp_dir))


@pytest.fixture
def in_temporary_runner_directory(tmp_path: Path):
    with tmpchdir(str(tmp_path)):
        yield


class TestInit:
    async def test_runner_respects_limit_setting(self):
        runner = Runner()
        assert runner.limit == PREFECT_RUNNER_PROCESS_LIMIT.value()

        runner = Runner(limit=50)
        assert runner.limit == 50

        with temporary_settings({PREFECT_RUNNER_PROCESS_LIMIT: 100}):
            runner = Runner()
            assert runner.limit == 100

    async def test_runner_limit_can_be_none(self):
        runner = Runner(limit=None)
        assert runner.limit is None

        # Be extra sure that the limiter is not initialized
        assert runner._limiter is None
        assert runner._acquire_limit_slot("foobar") is True

    async def test_runner_respects_poll_setting(self):
        runner = Runner()
        assert runner.query_seconds == PREFECT_RUNNER_POLL_FREQUENCY.value()

        runner = Runner(query_seconds=50)
        assert runner.query_seconds == 50

        with temporary_settings({PREFECT_RUNNER_POLL_FREQUENCY: 100}):
            runner = Runner()
            assert runner.query_seconds == 100

    async def test_runner_respects_heartbeat_setting(self):
        runner = Runner()
        assert runner.heartbeat_seconds == PREFECT_RUNNER_HEARTBEAT_FREQUENCY.value()
        assert runner.heartbeat_seconds is None

        with pytest.raises(
            ValueError, match="Heartbeat must be 30 seconds or greater."
        ):
            Runner(heartbeat_seconds=29)

        runner = Runner(heartbeat_seconds=50)
        assert runner.heartbeat_seconds == 50

        with temporary_settings({PREFECT_RUNNER_HEARTBEAT_FREQUENCY: 100}):
            runner = Runner()
            assert runner.heartbeat_seconds == 100


class TestServe:
    @pytest.fixture(autouse=True)
    async def mock_runner_start(self, monkeypatch: pytest.MonkeyPatch):
        mock = AsyncMock()
        monkeypatch.setattr("prefect.runner.Runner.start", mock)
        return mock

    def test_serve_prints_help_message_on_startup(
        self, capsys: pytest.CaptureFixture[str]
    ):
        serve(
            dummy_flow_1.to_deployment(__file__),
            dummy_flow_2.to_deployment(__file__),
            ClassNameStaticmethod.dummy_flow_staticmethod.to_deployment(__file__),
            ClassNameClassmethod.dummy_flow_classmethod.to_deployment(__file__),
            tired_flow.to_deployment(__file__),
        )

        captured = capsys.readouterr()

        assert (
            "Your deployments are being served and polling for scheduled runs!"
            in captured.out
        )
        assert "dummy-flow-1/test_runner" in captured.out
        assert "dummy-flow-2/test_runner" in captured.out
        assert "dummy-flow-staticmethod/test_runner" in captured.out
        assert "dummy-flow-classmethod/test_runner" in captured.out
        assert "tired-flow/test_runner" in captured.out
        assert "$ prefect deployment run [DEPLOYMENT_NAME]" in captured.out

    is_python_38 = sys.version_info[:2] == (3, 8)

    def test_serve_raises_if_runner_deployment_sets_work_pool_name(
        self, capsys: pytest.CaptureFixture[str]
    ):
        with pytest.warns(
            UserWarning, match="Work pools are not necessary for served deployments"
        ):
            serve(dummy_flow_1.to_deployment(__file__, work_pool_name="foo"))

    def test_serve_typed_container_inputs_flow(
        self, capsys: pytest.CaptureFixture[str]
    ):
        if self.is_python_38:

            @flow
            def type_container_input_flow(arg1: List[str]) -> str:
                print(arg1)
                return ",".join(arg1)

        else:

            @flow
            def type_container_input_flow(arg1: List[str]) -> str:
                print(arg1)
                return ",".join(arg1)

        serve(
            type_container_input_flow.to_deployment(__file__),
        )

        captured = capsys.readouterr()

        assert (
            "Your deployments are being served and polling for scheduled runs!"
            in captured.out
        )
        assert "type-container-input-flow/test_runner" in captured.out
        assert "$ prefect deployment run [DEPLOYMENT_NAME]" in captured.out

    def test_serve_can_create_multiple_deployments(
        self,
        sync_prefect_client: SyncPrefectClient,
    ):
        deployment_1 = dummy_flow_1.to_deployment(__file__, interval=3600)
        deployment_2 = dummy_flow_2.to_deployment(__file__, cron="* * * * *")

        serve(deployment_1, deployment_2)

        deployment = sync_prefect_client.read_deployment_by_name(
            name="dummy-flow-1/test_runner"
        )

        assert deployment is not None
        assert deployment.schedules[0].schedule.interval == datetime.timedelta(
            seconds=3600
        )

        deployment = sync_prefect_client.read_deployment_by_name(
            name="dummy-flow-2/test_runner"
        )

        assert deployment is not None
        assert deployment.schedules[0].schedule.cron == "* * * * *"

    def test_serve_starts_a_runner(
        self, prefect_client: PrefectClient, mock_runner_start: AsyncMock
    ):
        deployment = dummy_flow_1.to_deployment("test")

        serve(deployment)

        mock_runner_start.assert_awaited_once()

    def test_log_level_lowercasing(self, monkeypatch: pytest.MonkeyPatch):
        runner_mock = mock.MagicMock()
        log_level = "DEBUG"

        # Mock build_server to return a webserver mock object
        with mock.patch(
            "prefect.runner.server.build_server", new_callable=mock.AsyncMock
        ) as mock_build_server:
            webserver_mock = mock.MagicMock()
            mock_build_server.return_value = webserver_mock

            # Patch uvicorn.run to verify it's called with the correct arguments
            with mock.patch("uvicorn.run") as mock_uvicorn:
                start_webserver(runner_mock, log_level=log_level)
                # Assert build_server was called once with the runner
                mock_build_server.assert_called_once_with(runner_mock)

                # Assert uvicorn.run was called with the lowercase log_level and the webserver mock
                mock_uvicorn.assert_called_once_with(
                    webserver_mock, host=mock.ANY, port=mock.ANY, log_level="debug"
                )

    def test_serve_in_async_context_raises_error(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            "asyncio.get_running_loop", lambda: asyncio.get_event_loop()
        )

        deployment = dummy_flow_1.to_deployment("test")

        with pytest.raises(
            RuntimeError,
            match="Cannot call `serve` in an asynchronous context. Use `aserve` instead.",
        ):
            serve(deployment)


class TestAServe:
    @pytest.fixture(autouse=True)
    async def mock_runner_start(self, monkeypatch: pytest.MonkeyPatch):
        mock = AsyncMock()
        monkeypatch.setattr("prefect.runner.Runner.start", mock)
        return mock

    async def test_aserve_prints_help_message_on_startup(
        self, capsys: pytest.CaptureFixture[str]
    ):
        await aserve(
            await dummy_flow_1.to_deployment(__file__),
            await dummy_flow_2.to_deployment(__file__),
            await ClassNameStaticmethod.dummy_flow_staticmethod.to_deployment(__file__),
            await ClassNameClassmethod.dummy_flow_classmethod.to_deployment(__file__),
            await tired_flow.to_deployment(__file__),
        )

        captured = capsys.readouterr()

        assert (
            "Your deployments are being served and polling for scheduled runs!"
            in captured.out
        )
        assert "dummy-flow-1/test_runner" in captured.out
        assert "dummy-flow-2/test_runner" in captured.out
        assert "dummy-flow-staticmethod/test_runner" in captured.out
        assert "dummy-flow-classmethod/test_runner" in captured.out
        assert "tired-flow/test_runner" in captured.out
        assert "$ prefect deployment run [DEPLOYMENT_NAME]" in captured.out

    async def test_aserve_typed_container_inputs_flow(
        self, capsys: pytest.CaptureFixture[str]
    ):
        @flow
        def type_container_input_flow(arg1: List[str]) -> str:
            print(arg1)
            return ",".join(arg1)

        await aserve(
            await type_container_input_flow.to_deployment(__file__),
        )

        captured = capsys.readouterr()

        assert (
            "Your deployments are being served and polling for scheduled runs!"
            in captured.out
        )
        assert "type-container-input-flow/test_runner" in captured.out
        assert "$ prefect deployment run [DEPLOYMENT_NAME]" in captured.out

    async def test_aserve_can_create_multiple_deployments(
        self,
        prefect_client: PrefectClient,
    ):
        deployment_1 = dummy_flow_1.to_deployment(__file__, interval=3600)
        deployment_2 = dummy_flow_2.to_deployment(__file__, cron="* * * * *")

        await aserve(await deployment_1, await deployment_2)

        deployment = await prefect_client.read_deployment_by_name(
            name="dummy-flow-1/test_runner"
        )

        assert deployment is not None
        assert deployment.schedules[0].schedule.interval == datetime.timedelta(
            seconds=3600
        )

        deployment = await prefect_client.read_deployment_by_name(
            name="dummy-flow-2/test_runner"
        )

        assert deployment is not None
        assert deployment.schedules[0].schedule.cron == "* * * * *"

    async def test_aserve_starts_a_runner(
        self, prefect_client: PrefectClient, mock_runner_start: AsyncMock
    ):
        deployment = dummy_flow_1.to_deployment("test")

        await aserve(await deployment)

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
        assert deployment_1.schedules[0].schedule.interval == datetime.timedelta(
            seconds=3600
        )

        assert deployment_2 is not None
        assert deployment_2.name == "test_runner"
        assert deployment_2.schedules[0].schedule.cron == "* * * * *"

    async def test_add_flow_to_runner_always_updates_openapi_schema(
        self, prefect_client: PrefectClient
    ):
        """Runner.add should create a deployment for the flow passed to it"""
        runner = Runner()

        @flow
        def one(num: int):
            pass

        deployment_id = await runner.add_flow(one, name="test-openapi")
        deployment = await prefect_client.read_deployment(deployment_id)

        assert deployment.name == "test-openapi"
        assert deployment.description == "None"
        assert set(deployment.parameter_openapi_schema["properties"].keys()) == {"num"}

        @flow(name="one")
        def two(num: int):
            "description now"
            pass

        deployment_id = await runner.add_flow(two, name="test-openapi")
        deployment = await prefect_client.read_deployment(deployment_id)

        assert deployment.name == "test-openapi"
        assert deployment.description == "description now"
        assert set(deployment.parameter_openapi_schema["properties"].keys()) == {"num"}

        @flow(name="one")
        def three(name: str):
            pass

        deployment_id = await runner.add_flow(three, name="test-openapi")
        deployment = await prefect_client.read_deployment(deployment_id)

        assert deployment.name == "test-openapi"
        assert deployment.description is None
        assert set(deployment.parameter_openapi_schema["properties"].keys()) == {"name"}

    async def test_runner_deployment_updates_pull_steps(
        self, prefect_client: PrefectClient, work_pool
    ):
        @flow
        def one(num: int):
            pass

        deployment = RunnerDeployment(
            name="test-pullsteps",
            flow_name="one",
            work_pool_name=work_pool.name,
            storage=_PullStepStorage(
                pull_steps=[dict(name="step-one"), dict(name="step-two")]
            ),
        )

        deployment_id = await deployment.apply()
        api_deployment = await prefect_client.read_deployment(deployment_id)

        assert api_deployment.name == "test-pullsteps"
        assert api_deployment.pull_steps == [
            dict(name="step-one"),
            dict(name="step-two"),
        ]

        deployment = RunnerDeployment(
            name="test-pullsteps",
            flow_name="one",
            work_pool_name=work_pool.name,
            storage=_PullStepStorage(
                pull_steps=[dict(name="step-one"), dict(name="step-two-b")]
            ),
        )

        deployment_id = await deployment.apply()
        api_deployment = await prefect_client.read_deployment(deployment_id)

        assert api_deployment.name == "test-pullsteps"
        assert api_deployment.pull_steps == [
            dict(name="step-one"),
            dict(name="step-two-b"),
        ]

    async def test_runner_deployment_clears_pull_steps_when_storage_removed(
        self, prefect_client: PrefectClient, work_pool
    ):
        """Test that pull steps are cleared when storage is removed from a deployment.

        This addresses issue #18335 where pull steps would persist after removing
        storage, causing flow runs to fail.
        """

        @flow
        def test_flow():
            pass

        # Create deployment with storage
        deployment_with_storage = RunnerDeployment(
            name="test-clear-pullsteps",
            flow_name="test_flow",
            work_pool_name=work_pool.name,
            storage=_PullStepStorage(
                pull_steps=[dict(name="step-one"), dict(name="step-two")]
            ),
        )

        deployment_id = await deployment_with_storage.apply()
        api_deployment = await prefect_client.read_deployment(deployment_id)

        # Verify pull steps exist
        assert api_deployment.pull_steps == [
            dict(name="step-one"),
            dict(name="step-two"),
        ]

        # Update deployment without storage (simulating switch to Docker)
        deployment_no_storage = RunnerDeployment(
            name="test-clear-pullsteps",
            flow_name="test_flow",
            work_pool_name=work_pool.name,
            # No storage - pull steps should be cleared
        )

        await deployment_no_storage.apply()
        api_deployment = await prefect_client.read_deployment(deployment_id)

        # Verify pull steps were cleared
        assert api_deployment.pull_steps is None

    @pytest.mark.parametrize(
        "kwargs",
        [
            {**d1, **d2}
            for d1, d2 in combinations(
                [
                    {"interval": 3600},
                    {"cron": "* * * * *"},
                    {"rrule": "FREQ=MINUTELY"},
                    {
                        "schedules": [
                            DeploymentScheduleCreate(
                                schedule=CronSchedule(cron="* * * * *"), active=True
                            )
                        ]
                    },
                    {"schedule": Cron("* * * * *")},
                ],
                2,
            )
        ],
    )
    async def test_add_flow_raises_on_multiple_schedule_parameters(self, kwargs):
        with warnings.catch_warnings():
            # `schedule` parameter is deprecated and will raise a warning
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            expected_message = "Only one of interval, cron, rrule, schedule, or schedules can be provided."
            runner = Runner()
            with pytest.raises(ValueError, match=expected_message):
                await runner.add_flow(dummy_flow_1, __file__, **kwargs)

    async def test_add_deployments_to_runner(self, prefect_client: PrefectClient):
        """Runner.add_deployment should apply the deployment passed to it"""
        runner = Runner()

        deployment_1 = await dummy_flow_1.to_deployment(__file__, interval=3600)
        deployment_2 = await dummy_flow_2.to_deployment(__file__, cron="* * * * *")

        deployment_id_1 = await runner.add_deployment(deployment_1)
        deployment_id_2 = await runner.add_deployment(deployment_2)

        deployment_1 = await prefect_client.read_deployment(deployment_id_1)
        deployment_2 = await prefect_client.read_deployment(deployment_id_2)

        assert deployment_1 is not None
        assert deployment_1.name == "test_runner"
        assert deployment_1.schedules[0].schedule.interval == datetime.timedelta(
            seconds=3600
        )

        assert deployment_2 is not None
        assert deployment_2.name == "test_runner"
        assert deployment_2.schedules[0].schedule.cron == "* * * * *"

    async def test_runner_can_pause_schedules_on_stop(
        self, prefect_client: PrefectClient, caplog
    ):
        runner = Runner()

        deployment_1 = await dummy_flow_1.to_deployment(__file__, interval=3600)
        deployment_2 = await dummy_flow_2.to_deployment(__file__, cron="* * * * *")

        await runner.add_deployment(deployment_1)
        await runner.add_deployment(deployment_2)

        deployment_1 = await prefect_client.read_deployment_by_name(
            name="dummy-flow-1/test_runner"
        )
        deployment_2 = await prefect_client.read_deployment_by_name(
            name="dummy-flow-2/test_runner"
        )

        assert not deployment_1.paused

        assert not deployment_2.paused

        await runner.start(run_once=True)

        deployment_1 = await prefect_client.read_deployment_by_name(
            name="dummy-flow-1/test_runner"
        )
        deployment_2 = await prefect_client.read_deployment_by_name(
            name="dummy-flow-2/test_runner"
        )

        assert deployment_1.paused

        assert deployment_2.paused

        assert "Pausing all deployments" in caplog.text
        assert "All deployments have been paused" in caplog.text

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_does_not_emit_heartbeats_if_not_set(
        self,
        prefect_client: PrefectClient,
        mock_events_client: AssertingEventsClient,
    ):
        runner = Runner()

        deployment = await dummy_flow_1.to_deployment(__file__)

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

        assert flow_run.state
        assert flow_run.state.is_completed()

        heartbeat_events = list(
            filter(
                lambda e: e.event == "prefect.flow-run.heartbeat",
                mock_events_client.events,
            )
        )
        assert len(heartbeat_events) == 0

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_executes_flow_runs(
        self,
        prefect_client: PrefectClient,
        mock_events_client: AssertingEventsClient,
    ):
        runner = Runner(heartbeat_seconds=30)

        deployment = await dummy_flow_1.to_deployment(__file__)

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

        assert flow_run.state
        assert flow_run.state.is_completed()

        heartbeat_events = list(
            filter(
                lambda e: e.event == "prefect.flow-run.heartbeat",
                mock_events_client.events,
            )
        )
        assert len(heartbeat_events) == 1
        assert heartbeat_events[0].resource.id == f"prefect.flow-run.{flow_run.id}"

        related = [dict(r.items()) for r in heartbeat_events[0].related]

        assert related == [
            {
                "prefect.resource.id": f"prefect.deployment.{deployment.id}",
                "prefect.resource.role": "deployment",
                "prefect.resource.name": "test_runner",
            },
            {
                "prefect.resource.id": f"prefect.flow.{flow_run.flow_id}",
                "prefect.resource.role": "flow",
                "prefect.resource.name": dummy_flow_1.name,
            },
        ]

    async def test_runner_does_not_duplicate_heartbeats(
        self,
        prefect_client: PrefectClient,
        mock_events_client: AssertingEventsClient,
    ):
        """
        Regression test for issue where multiple invocations of `execute_flow_run`
        would result in multiple heartbeats being emitted for each flow run.
        """
        deployment_id = await (await dummy_flow_1.to_deployment(__file__)).apply()

        flow_run_1 = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )
        flow_run_2 = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )
        async with Runner(heartbeat_seconds=30, limit=None) as runner:
            first_task = asyncio.create_task(runner.execute_flow_run(flow_run_1.id))
            second_task = asyncio.create_task(runner.execute_flow_run(flow_run_2.id))

            await asyncio.gather(first_task, second_task)

        flow_run_1 = await prefect_client.read_flow_run(flow_run_id=flow_run_1.id)
        assert flow_run_1.state
        assert flow_run_1.state.is_completed()

        flow_run_2 = await prefect_client.read_flow_run(flow_run_id=flow_run_2.id)
        assert flow_run_2.state
        assert flow_run_2.state.is_completed()

        heartbeat_events = list(
            filter(
                lambda e: e.event == "prefect.flow-run.heartbeat",
                mock_events_client.events,
            )
        )
        assert len(heartbeat_events) == 2
        assert {e.resource.id for e in heartbeat_events} == {
            f"prefect.flow-run.{flow_run_1.id}",
            f"prefect.flow-run.{flow_run_2.id}",
        }

    async def test_runner_sends_heartbeats_on_a_cadence(
        self,
        prefect_client: PrefectClient,
        mock_events_client: AssertingEventsClient,
    ):
        runner = Runner()
        # Ain't I a stinker?
        runner.heartbeat_seconds = 1

        deployment_id = await (
            await short_but_not_too_short.to_deployment(__file__)
        ).apply()

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        await runner.execute_flow_run(flow_run.id)

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)

        assert flow_run.state
        assert flow_run.state.is_completed()

        heartbeat_events = list(
            filter(
                lambda e: e.event == "prefect.flow-run.heartbeat",
                mock_events_client.events,
            )
        )

        # We should get at least 5 heartbeats since the flow should take about 5 seconds to run
        assert len(heartbeat_events) > 5

    async def test_runner_heartbeats_include_deployment_version(
        self,
        prefect_client: PrefectClient,
        mock_events_client: AssertingEventsClient,
    ):
        runner = Runner(heartbeat_seconds=30)

        await runner.add_deployment(await dummy_flow_1.to_deployment(__file__))

        # mock the client to return a DeploymentResponse with a version_id and
        # version_info, which would be the case if the deployment was created Prefect
        # Cloud experimental deployment versioning support.
        deployment = await prefect_client.read_deployment_by_name(
            name="dummy-flow-1/test_runner"
        )
        deployment.version_id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        deployment.version_info = VersionInfo(
            type="githubulous",
            version="1.2.3.4.5.6",
        )

        with mock.patch(
            "prefect.client.orchestration.PrefectClient.read_deployment"
        ) as mock_read_deployment:
            mock_read_deployment.return_value = deployment

            await prefect_client.create_flow_run_from_deployment(
                deployment_id=deployment.id
            )
            await runner.start(run_once=True)

        heartbeat_events: list[Event] = list(
            filter(
                lambda e: e.event == "prefect.flow-run.heartbeat",
                mock_events_client.events,
            )
        )
        assert len(heartbeat_events) == 1

        heartbeat = heartbeat_events[0]

        resource = heartbeat.resource_in_role["deployment"]

        assert resource["prefect.resource.id"] == f"prefect.deployment.{deployment.id}"
        assert (
            resource["prefect.deployment.version-id"]
            == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        )
        assert resource["prefect.deployment.version-type"] == "githubulous"
        assert resource["prefect.deployment.version"] == "1.2.3.4.5.6"

    async def test_runner_does_not_try_to_cancel_flow_run_if_no_process_id_is_found(
        self, prefect_client: PrefectClient
    ):
        """
        Regression test for https://github.com/PrefectHQ/prefect/issues/18106
        """
        runner_1 = Runner()
        runner_2 = Runner()
        runner_2._mark_flow_run_as_cancelled = AsyncMock()
        runner_2._kill_process = AsyncMock()
        deployment_id = await runner_1.add_deployment(
            await tired_flow.to_deployment(__file__)
        )

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        async with runner_1, runner_2:
            execute_task = asyncio.create_task(runner_1.execute_flow_run(flow_run.id))

            while True:
                await anyio.sleep(0.5)
                flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
                assert flow_run.state
                if flow_run.state.is_running():
                    break

            await prefect_client.set_flow_run_state(
                flow_run_id=flow_run.id,
                state=flow_run.state.model_copy(
                    update={"name": "Cancelling", "type": StateType.CANCELLING}
                ),
            )

            await execute_task

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert flow_run.state.is_cancelled()
        runner_2._mark_flow_run_as_cancelled.assert_not_called()
        runner_2._kill_process.assert_not_called()

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_runs_on_cancellation_hooks_for_remotely_stored_flows(
        self,
        prefect_client: PrefectClient,
        caplog: pytest.LogCaptureFixture,
        in_temporary_runner_directory: None,
        temp_storage: MockStorage,
    ):
        runner = Runner(query_seconds=1)

        temp_storage.code = dedent(
            """\
            from time import sleep

            from prefect import flow
            from prefect.logging.loggers import flow_run_logger

            def on_cancellation(flow, flow_run, state):
                logger = flow_run_logger(flow_run, flow)
                logger.info("This flow was cancelled!")

            @flow(on_cancellation=[on_cancellation], log_prints=True)
            def cancel_flow(sleep_time: int = 100):
                sleep(sleep_time)
            """
        )

        deployment_id = await runner.add_flow(
            await flow.from_source(
                source=temp_storage, entrypoint="flows.py:cancel_flow"
            ),
            name=__file__,
        )

        async with runner:
            flow_run = await prefect_client.create_flow_run_from_deployment(
                deployment_id=deployment_id
            )

            execute_task = asyncio.create_task(runner.execute_flow_run(flow_run.id))
            # Need to wait for polling loop to pick up flow run and
            # start execution
            while True:
                await anyio.sleep(0.5)
                flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
                assert flow_run.state
                if flow_run.state.is_running():
                    break

            await prefect_client.set_flow_run_state(
                flow_run_id=flow_run.id,
                state=flow_run.state.model_copy(
                    update={"name": "Cancelling", "type": StateType.CANCELLING}
                ),
            )

            await execute_task

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert flow_run.state.is_cancelled()
        # check to make sure on_cancellation hook was called
        assert "This flow was cancelled!" in caplog.text

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_warns_if_unable_to_load_cancellation_hooks(
        self,
        prefect_client: PrefectClient,
        caplog: pytest.LogCaptureFixture,
        in_temporary_runner_directory: None,
        temp_storage: MockStorage,
    ):
        runner = Runner(query_seconds=2)

        temp_storage.code = dedent(
            """\
            from time import sleep

            from prefect import flow
            from prefect.logging.loggers import flow_run_logger

            def on_cancellation(flow, flow_run, state):
                logger = flow_run_logger(flow_run, flow)
                logger.info("This flow was cancelled!")

            @flow(on_cancellation=[on_cancellation], log_prints=True)
            def cancel_flow(sleep_time: int = 100):
                sleep(sleep_time)
            """
        )

        deployment_id = await runner.add_flow(
            await flow.from_source(
                source=temp_storage, entrypoint="flows.py:cancel_flow"
            ),
            name=__file__,
        )

        async with runner:
            flow_run = await prefect_client.create_flow_run_from_deployment(
                deployment_id=deployment_id
            )

            execute_task = asyncio.create_task(runner.execute_flow_run(flow_run.id))
            # Need to wait for polling loop to pick up flow run and
            # start execution
            while True:
                await anyio.sleep(0.5)
                flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
                assert flow_run.state
                if flow_run.state.is_running():
                    break

            await prefect_client.delete_deployment(deployment_id=deployment_id)

            await prefect_client.set_flow_run_state(
                flow_run_id=flow_run.id,
                state=flow_run.state.model_copy(
                    update={"name": "Cancelling", "type": StateType.CANCELLING}
                ),
            )

            await execute_task

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)

        # Cancellation hook should not have been called successfully
        # but the flow run should still be cancelled correctly
        assert flow_run.state.is_cancelled()
        assert "This flow was cancelled!" not in caplog.text
        assert (
            "Runner failed to retrieve flow to execute on_cancellation hooks for flow run"
            in caplog.text
        )

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_runs_on_crashed_hooks_for_remotely_stored_flows(
        self,
        prefect_client: PrefectClient,
        caplog: pytest.LogCaptureFixture,
        in_temporary_runner_directory: None,
        temp_storage: MockStorage,
    ):
        runner = Runner()
        temp_storage.code = dedent(
            """\
        import os
        import signal

        from prefect import flow
        from prefect.logging.loggers import flow_run_logger

        def on_crashed(flow, flow_run, state):
            logger = flow_run_logger(flow_run, flow)
            logger.info("This flow crashed!")

        @flow(on_crashed=[on_crashed], log_prints=True)
        def crashing_flow():
            print("Oh boy, here I go crashing again...")
            os.kill(os.getpid(), signal.SIGTERM)
        """
        )

        deployment_id = await runner.add_flow(
            await flow.from_source(
                source=temp_storage, entrypoint="flows.py:crashing_flow"
            ),
            name=__file__,
        )

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )
        await runner.execute_flow_run(flow_run.id)

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert flow_run.state
        assert flow_run.state.is_crashed()
        # check to make sure on_cancellation hook was called
        assert "This flow crashed!" in caplog.text

    @pytest.mark.parametrize(
        "exception,hook_type",
        [
            # Test various exceptions that can occur when loading flows
            (
                ScriptError(
                    user_exc=FileNotFoundError("File not found"), path="/missing.py"
                ),
                "crashed",
            ),
            (ValueError("Flow run does not have an associated deployment"), "crashed"),
            (RuntimeError("Unexpected error!"), "crashed"),
            # Also test cancellation hooks
            (
                ScriptError(
                    user_exc=FileNotFoundError("File not found"), path="/missing.py"
                ),
                "cancellation",
            ),
        ],
    )
    async def test_runner_handles_exceptions_in_hooks(
        self,
        exception,
        hook_type,
        caplog: pytest.LogCaptureFixture,
    ):
        """Test that exceptions during flow loading don't crash the runner"""

        runner = Runner()

        # Create a mock flow run
        mock_flow_run = MagicMock()
        mock_flow_run.id = "test-flow-run-id"
        mock_flow_run.deployment_id = "test-deployment-id"
        mock_flow_run.name = "test-flow-run"

        # Mock load_flow_from_flow_run to raise the exception
        with patch(
            "prefect.runner.runner.load_flow_from_flow_run", side_effect=exception
        ):
            # Run the appropriate hook method
            if hook_type == "crashed":
                state = Crashed(message="Test crash")
                await runner._run_on_crashed_hooks(mock_flow_run, state)
                expected_msg = (
                    "Runner failed to retrieve flow to execute on_crashed hooks"
                )
            else:
                state = Cancelling(message="Test cancellation")
                await runner._run_on_cancellation_hooks(mock_flow_run, state)
                expected_msg = (
                    "Runner failed to retrieve flow to execute on_cancellation hooks"
                )

        # Verify warning was logged with exception details
        assert expected_msg in caplog.text
        assert type(exception).__name__ in caplog.text

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_does_not_emit_heartbeats_for_single_flow_run_if_not_set(
        self, prefect_client: PrefectClient, mock_events_client: AssertingEventsClient
    ):
        runner = Runner()

        deployment_id = await (await dummy_flow_1.to_deployment(__file__)).apply()

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )
        await runner.execute_flow_run(flow_run.id)

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert flow_run.state
        assert flow_run.state.is_completed()

        heartbeat_events = list(
            filter(
                lambda e: e.event == "prefect.flow-run.heartbeat",
                mock_events_client.events,
            )
        )
        assert len(heartbeat_events) == 0

    @pytest.mark.usefixtures("use_hosted_api_server")
    @pytest.mark.parametrize(
        "dummy_flow",
        [
            dummy_flow_1,
            ClassNameClassmethod.dummy_flow_classmethod,
            ClassNameStaticmethod.dummy_flow_staticmethod,
        ],
    )
    async def test_runner_can_execute_a_single_flow_run(
        self,
        dummy_flow: Flow,
        prefect_client: PrefectClient,
        mock_events_client: AssertingEventsClient,
    ):
        runner = Runner(heartbeat_seconds=30, limit=None)

        deployment_id = await (await dummy_flow.to_deployment(__file__)).apply()

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )
        await runner.execute_flow_run(flow_run.id)

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert flow_run.state
        assert flow_run.state.is_completed()

        heartbeat_events = list(
            filter(
                lambda e: e.event == "prefect.flow-run.heartbeat",
                mock_events_client.events,
            )
        )
        assert len(heartbeat_events) == 1
        assert heartbeat_events[0].resource.id == f"prefect.flow-run.{flow_run.id}"

        related = [dict(r.items()) for r in heartbeat_events[0].related]

        assert related == [
            {
                "prefect.resource.id": f"prefect.deployment.{deployment_id}",
                "prefect.resource.role": "deployment",
                "prefect.resource.name": "test_runner",
            },
            {
                "prefect.resource.id": f"prefect.flow.{flow_run.flow_id}",
                "prefect.resource.role": "flow",
                "prefect.resource.name": dummy_flow.name,
            },
        ]

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_respects_set_limit(
        self, prefect_client: PrefectClient, caplog
    ):
        async with Runner(limit=1) as runner:
            deployment_id = await (await dummy_flow_1.to_deployment(__file__)).apply()

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

    async def test_handles_spaces_in_sys_executable(self, monkeypatch, prefect_client):
        """
        Regression test for https://github.com/PrefectHQ/prefect/issues/10820
        """
        import sys

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.pid = 4242

        mock_run_process_call = AsyncMock(
            return_value=mock_process,
        )

        monkeypatch.setattr(prefect.runner.runner, "run_process", mock_run_process_call)

        monkeypatch.setattr(sys, "executable", "C:/Program Files/Python38/python.exe")

        runner = Runner()

        deployment_id = await (await dummy_flow_1.to_deployment(__file__)).apply()

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )
        await runner._run_process(flow_run)

        # Previously the command would have been
        # ["C:/Program", "Files/Python38/python.exe", "-m", "prefect.engine"]
        assert mock_run_process_call.call_args[1]["command"] == [
            "C:/Program Files/Python38/python.exe",
            "-m",
            "prefect.engine",
        ]

    async def test_runner_sets_flow_run_env_var_with_dashes(
        self, monkeypatch, prefect_client
    ):
        """
        Regression test for https://github.com/PrefectHQ/prefect/issues/10851
        """
        env_var_value = None

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.pid = 4242

        def capture_env_var(*args, **kwargs):
            nonlocal env_var_value
            nonlocal mock_process
            env_var_value = kwargs["env"].get("PREFECT__FLOW_RUN_ID")
            return mock_process

        mock_run_process_call = AsyncMock(side_effect=capture_env_var)

        monkeypatch.setattr(prefect.runner.runner, "run_process", mock_run_process_call)

        runner = Runner()

        deployment_id = await (await dummy_flow_1.to_deployment(__file__)).apply()

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )
        await runner._run_process(flow_run)

        assert env_var_value == str(flow_run.id)
        assert env_var_value != flow_run.id.hex

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_runs_a_remotely_stored_flow(
        self,
        prefect_client: PrefectClient,
        temp_storage: MockStorage,
    ):
        runner = Runner()

        deployment = await (
            await flow.from_source(source=temp_storage, entrypoint="flows.py:test_flow")
        ).to_deployment(__file__)

        deployment_id = await runner.add_deployment(deployment)

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        await runner.start(run_once=True)
        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)

        assert flow_run.state
        assert flow_run.state.is_completed()

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_caches_adhoc_pulls(self, prefect_client):
        runner = Runner()

        pull_code_spy = MagicMock()

        with tempfile.TemporaryDirectory() as temp_dir:
            storage = MockStorage(base_path=Path(temp_dir), pull_code_spy=pull_code_spy)
            deployment = await RunnerDeployment.afrom_storage(
                storage=storage,
                entrypoint="flows.py:test_flow",
                name=__file__,
            )

            deployment_id = await runner.add_deployment(deployment)

        await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        await runner.start(run_once=True)

        # 1 for deployment creation, 1 for runner start up, 1 for ad hoc pull
        assert isinstance(runner._storage_objs[0], MockStorage)
        assert runner._storage_objs[0]._pull_code_spy is not None
        assert runner._storage_objs[0]._pull_code_spy.call_count == 3

        await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        # Should be 3 because the ad hoc pull should have been cached
        assert runner._storage_objs[0]._pull_code_spy.call_count == 3

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_does_not_raise_on_duplicate_submission(self, prefect_client):
        """
        Regression test for https://github.com/PrefectHQ/prefect/issues/11093

        The runner has a race condition where it can try to borrow a limit slot
        that it already has. This test ensures that the runner does not raise
        an exception in this case.
        """
        async with Runner(pause_on_shutdown=False) as runner:
            deployment = RunnerDeployment.from_flow(
                flow=tired_flow,
                name=__file__,
            )

            deployment_id = await runner.add_deployment(deployment)

            flow_run = await prefect_client.create_flow_run_from_deployment(
                deployment_id=deployment_id
            )
            # acquire the limit slot and then try to borrow it again
            # during submission to simulate race condition
            runner._acquire_limit_slot(flow_run.id)
            await runner._get_and_submit_flow_runs()

            # shut down cleanly
            runner.started = False
            runner.stopping = True
            runner._cancelling_flow_run_ids.add(flow_run.id)
            await runner._cancel_run(flow_run)

    @pytest.mark.parametrize(
        "exit_code,help_message",
        [
            (-9, "This indicates that the process exited due to a SIGKILL signal"),
            (
                247,
                "This indicates that the process was terminated due to high memory usage.",
            ),
        ],
    )
    async def test_runner_logs_exit_code_help_message(
        self,
        exit_code: int,
        help_message: str,
        caplog: pytest.LogCaptureFixture,
        patch_run_process: MagicMock,
        prefect_client: PrefectClient,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        # Change directory to avoid polluting the working directory
        monkeypatch.chdir(str(tmp_path))
        flow_id = await prefect_client.create_flow(
            flow=dummy_flow_1,
        )
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name=f"test-runner-deployment-{uuid.uuid4()}",
            path=str(
                prefect.__development_base_path__
                / "tests"
                / "test-projects"
                / "import-project"
            ),
            entrypoint="my_module/flow.py:test_flow",
        )

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id,
        )

        patch_run_process(returncode=exit_code)
        async with Runner() as runner:
            result = await runner.execute_flow_run(
                flow_run_id=flow_run.id,
            )

        assert result
        assert result.returncode == exit_code

        record = next(r for r in caplog.records if help_message in r.message)
        if exit_code == -9:
            assert record.levelname == "INFO"
        else:
            assert record.levelname == "ERROR"

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="subprocess.CREATE_NEW_PROCESS_GROUP is only defined in Windows",
    )
    async def test_windows_process_worker_run_sets_process_group_creation_flag(
        self,
        patch_run_process: MagicMock,
        prefect_client: PrefectClient,
    ):
        mock = patch_run_process()

        deployment = await dummy_flow_1.ato_deployment(__file__)
        deployment_id_coro = deployment.apply()
        if TYPE_CHECKING:
            assert isinstance(deployment_id_coro, Coroutine)
        deployment_id = await deployment_id_coro

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        async with Runner() as runner:
            await runner.execute_flow_run(
                flow_run_id=flow_run.id,
            )

        mock.assert_awaited_once()
        (_, kwargs) = mock.call_args
        assert kwargs.get("creationflags") == mock.CREATE_NEW_PROCESS_GROUP

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason=(
            "The asyncio.open_process_*.creationflags argument is only supported on Windows"
        ),
    )
    async def test_unix_process_worker_run_does_not_set_creation_flag(
        self, patch_run_process: MagicMock, prefect_client: PrefectClient
    ):
        mock = patch_run_process()
        deployment = await dummy_flow_1.ato_deployment(__file__)
        deployment_id_coro = deployment.apply()
        if TYPE_CHECKING:
            assert isinstance(deployment_id_coro, Coroutine)
        deployment_id = await deployment_id_coro

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        async with Runner() as runner:
            await runner.execute_flow_run(
                flow_run_id=flow_run.id,
            )

        mock.assert_awaited_once()
        (_, kwargs) = mock.call_args
        assert kwargs.get("creationflags") is None

    async def test_reschedule_flow_runs(
        self,
        monkeypatch: pytest.MonkeyPatch,
        prefect_client: PrefectClient,
    ):
        # Create a flow run that will take a while to run
        deployment_id = await (await tired_flow.to_deployment(__file__)).apply()

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        runner = Runner()

        # Run the flow run in a new process with a Runner
        execute_flow_run_task = asyncio.create_task(
            runner.execute_flow_run(flow_run_id=flow_run.id)
        )

        # Wait for the flow run to start
        while True:
            await anyio.sleep(0.5)
            flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
            assert flow_run.state
            if flow_run.state.is_running():
                break

        runner.reschedule_current_flow_runs()

        await execute_flow_run_task

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert flow_run.state
        assert flow_run.state.is_scheduled()

    async def test_runner_marks_flow_run_as_crashed_when_unabled_to_start_process(
        self, prefect_client: PrefectClient, monkeypatch: pytest.MonkeyPatch
    ):
        mock = AsyncMock(side_effect=Exception("Test error"))
        monkeypatch.setattr(prefect.runner.runner, "run_process", mock)
        runner = Runner()

        deployment_id = await (await dummy_flow_1.to_deployment(__file__)).apply()

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        await runner.execute_flow_run(flow_run_id=flow_run.id)

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert flow_run.state
        assert flow_run.state.is_crashed()

    async def test_runner_handles_output_stream_errors(
        self, prefect_client: PrefectClient, monkeypatch: pytest.MonkeyPatch
    ):
        """
        Regression test for https://github.com/PrefectHQ/prefect/issues/17316
        """
        # Simulate stream output error
        mock = AsyncMock(side_effect=Exception("Test error"))
        monkeypatch.setattr(processutils, "consume_process_output", mock)
        runner = Runner()

        deployment_id = await (await dummy_flow_1.to_deployment(__file__)).apply()

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        # Runner shouldn't crash
        await runner.execute_flow_run(flow_run_id=flow_run.id)

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert flow_run.state
        assert flow_run.state.is_completed()

    async def test_runner_temp_dir_creation_is_idempotent(self):
        """
        Test that Runner temp directory creation is idempotent
        and handles the case where the directory already exists.

        This tests the fix for the race condition where multiple flow runs
        could try to create the same temp directory when the runner is
        entered as a context manager.
        """
        runner = Runner()

        # Manually create the temp directory to simulate race condition
        runner._tmp_dir.mkdir(parents=True, exist_ok=False)

        # Now entering the runner context should not fail even though
        # the directory already exists (with exist_ok=True fix)
        async with runner:
            assert runner.started
            assert runner._tmp_dir.exists()

        # Directory should be cleaned up after exiting context
        assert not runner._tmp_dir.exists()

    class TestRunnerBundleExecution:
        @pytest.fixture(autouse=True)
        def mock_subprocess_check_call(self, monkeypatch: pytest.MonkeyPatch):
            mock_subprocess_check_call = AsyncMock()
            monkeypatch.setattr(subprocess, "check_call", mock_subprocess_check_call)
            return mock_subprocess_check_call

        async def test_basic(
            self, prefect_client: PrefectClient, mock_subprocess_check_call: AsyncMock
        ):
            runner = Runner()

            @flow(persist_result=True)
            def simple_flow():
                return "Be a simple kind of flow"

            flow_run = await prefect_client.create_flow_run(simple_flow)

            bundle = create_bundle_for_flow_run(simple_flow, flow_run)
            await runner.execute_bundle(bundle)

            flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
            assert flow_run.state
            assert flow_run.state.is_completed()
            assert await flow_run.state.result() == "Be a simple kind of flow"

            # Ensure that the dependencies are installed
            assert mock_subprocess_check_call.call_count == 1
            assert mock_subprocess_check_call.call_args[0][0][:3] == [
                uv.find_uv_bin(),
                "pip",
                "install",
            ]

        async def test_with_parameters(self, prefect_client: PrefectClient):
            runner = Runner()

            @flow(persist_result=True)
            def flow_with_parameters(x: int, y: str):
                return f"Be a simple kind of flow with {x} and {y}"

            flow_run = await prefect_client.create_flow_run(
                flow_with_parameters,
                parameters={"x": 42, "y": "hello"},
            )

            bundle = create_bundle_for_flow_run(flow_with_parameters, flow_run)
            await runner.execute_bundle(bundle)

            flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
            assert flow_run.state
            assert flow_run.state.is_completed()
            assert (
                await flow_run.state.result()
                == "Be a simple kind of flow with 42 and hello"
            )

        async def test_failed_flow(self, prefect_client: PrefectClient):
            runner = Runner()

            @flow
            def total_and_utter_failure():
                raise ValueError("This flow failed!")

            flow_run = await prefect_client.create_flow_run(total_and_utter_failure)

            bundle = create_bundle_for_flow_run(total_and_utter_failure, flow_run)
            await runner.execute_bundle(bundle)

            flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
            assert flow_run.state
            assert flow_run.state.is_failed()

        async def test_cancel_bundle_execution(
            self, prefect_client: PrefectClient, caplog: pytest.LogCaptureFixture
        ):
            runner = Runner(query_seconds=1)

            @flow
            def flow_to_cancel():
                sleep(100)

            @flow_to_cancel.on_cancellation
            def da_hook(
                flow: "Flow[Any, Any]", flow_run: "FlowRun", state: "State[Any]"
            ):
                flow_run_logger(flow_run, flow).info("This flow was cancelled!")

            flow_run = await prefect_client.create_flow_run(flow_to_cancel)

            bundle = create_bundle_for_flow_run(flow_to_cancel, flow_run)
            execution_task = asyncio.create_task(runner.execute_bundle(bundle))

            flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
            assert flow_run.state is not None
            while not flow_run.state.is_running():
                assert not execution_task.done(), (
                    "Execution ended earlier than expected"
                )
                flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
                assert flow_run.state is not None

            await prefect_client.set_flow_run_state(
                flow_run_id=flow_run.id,
                state=Cancelling(),
            )

            await execution_task

            flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
            assert flow_run.state
            assert flow_run.state.is_cancelled()

            assert "This flow was cancelled!" in caplog.text

        async def test_crashed_bundle_execution(
            self, prefect_client: PrefectClient, caplog: pytest.LogCaptureFixture
        ):
            runner = Runner()

            @flow
            def crashed_flow():
                os.kill(os.getpid(), signal.SIGTERM)

            @crashed_flow.on_crashed
            def da_hook(
                flow: "Flow[Any, Any]", flow_run: "FlowRun", state: "State[Any]"
            ):
                flow_run_logger(flow_run, flow).info("This flow crashed!")

            flow_run = await prefect_client.create_flow_run(crashed_flow)

            bundle = create_bundle_for_flow_run(crashed_flow, flow_run)
            await runner.execute_bundle(bundle)

            flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
            assert flow_run.state
            assert flow_run.state.is_crashed()

            assert "This flow crashed!" in caplog.text

        async def test_heartbeats_for_bundle_execution(
            self,
            prefect_client: PrefectClient,
            mock_events_client: AssertingEventsClient,
        ):
            runner = Runner(heartbeat_seconds=30)

            @flow
            def heartbeat_flow():
                return "a low, dull, quick sound — much such a sound as a watch makes when enveloped in cotton"

            flow_run = await prefect_client.create_flow_run(heartbeat_flow)

            bundle = create_bundle_for_flow_run(heartbeat_flow, flow_run)
            await runner.execute_bundle(bundle)

            flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
            assert flow_run.state
            assert flow_run.state.is_completed()

            heartbeat_events = list(
                filter(
                    lambda e: e.event == "prefect.flow-run.heartbeat",
                    mock_events_client.events,
                )
            )
            assert len(heartbeat_events) == 1
            assert heartbeat_events[0].resource.id == f"prefect.flow-run.{flow_run.id}"

            related = [dict(r.items()) for r in heartbeat_events[0].related]

            assert related == [
                {
                    "prefect.resource.id": f"prefect.flow.{flow_run.flow_id}",
                    "prefect.resource.role": "flow",
                    "prefect.resource.name": heartbeat_flow.name,
                },
            ]


@pytest.mark.usefixtures("use_hosted_api_server")
async def test_runner_emits_cancelled_event(
    mock_events_client: AssertingEventsClient,
    reset_worker_events,
    prefect_client: PrefectClient,
    temp_storage: MockStorage,
    in_temporary_runner_directory: None,
):
    runner = Runner(query_seconds=1)
    temp_storage.code = dedent(
        """\
        from time import sleep

        from prefect import flow
        from prefect.logging.loggers import flow_run_logger

        def on_cancellation(flow, flow_run, state):
            logger = flow_run_logger(flow_run, flow)
            logger.info("This flow was cancelled!")

        @flow(on_cancellation=[on_cancellation], log_prints=True)
        def cancel_flow(sleep_time: int = 100):
            sleep(sleep_time)
        """
    )

    deployment_id = await runner.add_flow(
        await flow.from_source(source=temp_storage, entrypoint="flows.py:cancel_flow"),
        name=__file__,
        tags=["test"],
    )
    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment_id,
        tags=["flow-run-one"],
    )
    api_flow = await prefect_client.read_flow(flow_run.flow_id)

    async with runner:
        execute_task = asyncio.create_task(
            runner.execute_flow_run(flow_run_id=flow_run.id)
        )
        while True:
            await anyio.sleep(0.5)
            flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
            assert flow_run.state
            if flow_run.state.is_running():
                break
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id,
            state=flow_run.state.model_copy(
                update={"name": "Cancelling", "type": StateType.CANCELLING}
            ),
        )
        await execute_task

    cancelled_events = list(
        filter(
            lambda e: e.event == "prefect.runner.cancelled-flow-run",
            mock_events_client.events,
        )
    )
    assert len(cancelled_events) == 1

    assert dict(cancelled_events[0].resource.items()) == {
        "prefect.resource.id": f"prefect.runner.{slugify(runner.name)}",
        "prefect.resource.name": runner.name,
        "prefect.version": str(__version__),
    }

    related = [dict(r.items()) for r in cancelled_events[0].related]

    assert related == [
        {
            "prefect.resource.id": f"prefect.deployment.{deployment_id}",
            "prefect.resource.role": "deployment",
            "prefect.resource.name": "test_runner",
        },
        {
            "prefect.resource.id": f"prefect.flow.{api_flow.id}",
            "prefect.resource.role": "flow",
            "prefect.resource.name": api_flow.name,
        },
        {
            "prefect.resource.id": f"prefect.flow-run.{flow_run.id}",
            "prefect.resource.role": "flow-run",
            "prefect.resource.name": flow_run.name,
        },
        {
            "prefect.resource.id": "prefect.tag.flow-run-one",
            "prefect.resource.role": "tag",
        },
        {
            "prefect.resource.id": "prefect.tag.test",
            "prefect.resource.role": "tag",
        },
    ]


class TestRunnerDeployment:
    @pytest.fixture
    def relative_file_path(self):
        return Path(__file__).relative_to(Path.cwd())

    @pytest.fixture
    def dummy_flow_1_entrypoint(self, relative_file_path):
        return f"{relative_file_path}:dummy_flow_1"

    @pytest.mark.parametrize(
        "dummy_flow, flow_name, entrypoint_suffix",
        [
            (
                dummy_flow_1,
                "dummy-flow-1",
                "dummy_flow_1",
            ),
            (
                ClassNameClassmethod.dummy_flow_classmethod,
                "dummy-flow-classmethod",
                "ClassNameClassmethod.dummy_flow_classmethod",
            ),
            (
                ClassNameStaticmethod.dummy_flow_staticmethod,
                "dummy-flow-staticmethod",
                "ClassNameStaticmethod.dummy_flow_staticmethod",
            ),
        ],
    )
    def test_from_flow(
        self,
        dummy_flow: Flow,
        flow_name: str,
        entrypoint_suffix: str,
        relative_file_path: Path,
    ):
        deployment = RunnerDeployment.from_flow(
            dummy_flow,
            __file__,
            tags=["test"],
            version="alpha",
            version_type=VersionType.SIMPLE,
            description="Deployment descriptions",
            enforce_parameter_schema=True,
            concurrency_limit=42,
        )

        assert deployment.name == "test_runner"
        assert deployment.flow_name == flow_name
        assert deployment.entrypoint == f"{relative_file_path}:{entrypoint_suffix}"
        assert deployment.description == "Deployment descriptions"
        assert deployment.version == "alpha"
        assert deployment.version_type == VersionType.SIMPLE
        assert deployment.tags == ["test"]
        assert deployment.paused is False
        assert deployment.enforce_parameter_schema
        assert deployment.concurrency_limit == 42

    async def test_from_flow_can_produce_a_module_path_entrypoint(self):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1,
            __file__,
            entrypoint_type=EntrypointType.MODULE_PATH,
        )

        assert (
            deployment.entrypoint
            == f"{dummy_flow_1.__module__}.{dummy_flow_1.__name__}"
        )

    def test_from_flow_accepts_interval(self):
        deployment = RunnerDeployment.from_flow(dummy_flow_1, __file__, interval=3600)
        assert deployment.schedules
        assert deployment.schedules[0].schedule.interval == datetime.timedelta(
            seconds=3600
        )

    def test_from_flow_accepts_interval_as_list(self):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1, __file__, interval=[3600, 7200]
        )
        assert deployment.schedules
        assert deployment.schedules[0].schedule.interval == datetime.timedelta(
            seconds=3600
        )
        assert deployment.schedules[1].schedule.interval == datetime.timedelta(
            seconds=7200
        )

    def test_from_flow_accepts_cron(self):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1, __file__, cron="* * * * *"
        )
        assert deployment.schedules
        assert deployment.schedules[0].schedule.cron == "* * * * *"

    def test_from_flow_accepts_cron_as_list(self):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1,
            __file__,
            cron=[
                "0 * * * *",
                "0 0 1 * *",
                "*/10 * * * *",
            ],
        )
        assert deployment.schedules
        assert deployment.schedules[0].schedule.cron == "0 * * * *"
        assert deployment.schedules[1].schedule.cron == "0 0 1 * *"
        assert deployment.schedules[2].schedule.cron == "*/10 * * * *"

    def test_from_flow_accepts_rrule(self):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1, __file__, rrule="FREQ=MINUTELY"
        )
        assert deployment.schedules
        assert deployment.schedules[0].schedule.rrule == "FREQ=MINUTELY"

    def test_from_flow_accepts_rrule_as_list(self):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1,
            __file__,
            rrule=[
                "FREQ=DAILY",
                "FREQ=WEEKLY",
                "FREQ=MONTHLY",
            ],
        )
        assert deployment.schedules
        assert deployment.schedules[0].schedule.rrule == "FREQ=DAILY"
        assert deployment.schedules[1].schedule.rrule == "FREQ=WEEKLY"
        assert deployment.schedules[2].schedule.rrule == "FREQ=MONTHLY"

    def test_from_flow_accepts_schedules(self):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1,
            __file__,
            schedules=[
                DeploymentScheduleCreate(
                    schedule=CronSchedule(cron="* * * * *"), active=True
                ),
                IntervalSchedule(interval=datetime.timedelta(days=1)),
                {
                    "schedule": IntervalSchedule(interval=datetime.timedelta(days=2)),
                    "active": False,
                },
                Interval(datetime.timedelta(days=3)),
            ],
        )
        assert deployment.schedules
        assert deployment.schedules[0].schedule.cron == "* * * * *"
        assert deployment.schedules[0].active is True
        assert deployment.schedules[1].schedule.interval == datetime.timedelta(days=1)
        assert deployment.schedules[1].active is True
        assert deployment.schedules[2].schedule.interval == datetime.timedelta(days=2)
        assert deployment.schedules[2].active is False
        assert deployment.schedules[3].schedule.interval == datetime.timedelta(days=3)
        assert deployment.schedules[3].active is True

    @pytest.mark.parametrize(
        "value,expected",
        [(True, True), (False, False), (None, False)],
    )
    def test_from_flow_accepts_paused(self, value, expected):
        deployment = RunnerDeployment.from_flow(dummy_flow_1, __file__, paused=value)

        assert deployment.paused is expected

    async def test_from_flow_accepts_concurrency_limit_config(self):
        concurrency_limit_config = ConcurrencyLimitConfig(
            limit=42, collision_strategy="CANCEL_NEW"
        )
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1,
            __file__,
            concurrency_limit=concurrency_limit_config,
        )
        assert deployment.concurrency_limit == concurrency_limit_config.limit
        assert (
            deployment.concurrency_options.collision_strategy
            == concurrency_limit_config.collision_strategy
        )

    @pytest.mark.parametrize(
        "kwargs",
        [
            {**d1, **d2}
            for d1, d2 in combinations(
                [
                    {"interval": 3600},
                    {"cron": "* * * * *"},
                    {"rrule": "FREQ=MINUTELY"},
                    {
                        "schedules": [
                            DeploymentScheduleCreate(
                                schedule=CronSchedule(cron="* * * * *"), active=True
                            )
                        ],
                    },
                    {"schedule": Cron("* * * * *")},
                ],
                2,
            )
        ],
    )
    def test_from_flow_raises_on_multiple_schedule_parameters(self, kwargs):
        expected_message = (
            "Only one of interval, cron, rrule, schedule, or schedules can be provided."
        )
        with pytest.raises(ValueError, match=expected_message):
            RunnerDeployment.from_flow(dummy_flow_1, __file__, **kwargs)

    def test_from_flow_uses_defaults_from_flow(self):
        deployment = RunnerDeployment.from_flow(dummy_flow_1, __file__)

        assert deployment.version == "test"
        assert deployment._version_from_flow is True
        assert deployment.description == "I'm just here for tests"

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
        da_flow.__module__ = "__not_a_real_module__"

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
        assert deployment.entrypoint == "tests/runner/test_runner.py:dummy_flow_1"
        assert deployment.description == "Deployment descriptions"
        assert deployment.version == "alpha"
        assert deployment.tags == ["test"]
        assert deployment.enforce_parameter_schema
        assert deployment.concurrency_limit is None

    def test_from_entrypoint_accepts_interval(self, dummy_flow_1_entrypoint):
        deployment = RunnerDeployment.from_entrypoint(
            dummy_flow_1_entrypoint, __file__, interval=3600
        )
        assert deployment.schedules
        assert deployment.schedules[0].schedule.interval == datetime.timedelta(
            seconds=3600
        )

    def test_from_entrypoint_accepts_interval_as_list(self, dummy_flow_1_entrypoint):
        deployment = RunnerDeployment.from_entrypoint(
            dummy_flow_1_entrypoint, __file__, interval=[3600, 7200]
        )
        assert deployment.schedules
        assert deployment.schedules[0].schedule.interval == datetime.timedelta(
            seconds=3600
        )
        assert deployment.schedules[1].schedule.interval == datetime.timedelta(
            seconds=7200
        )

    def test_from_entrypoint_accepts_cron(self, dummy_flow_1_entrypoint):
        deployment = RunnerDeployment.from_entrypoint(
            dummy_flow_1_entrypoint, __file__, cron="* * * * *"
        )
        assert deployment.schedules
        assert deployment.schedules[0].schedule.cron == "* * * * *"

    def test_from_entrypoint_accepts_cron_as_list(self, dummy_flow_1_entrypoint):
        deployment = RunnerDeployment.from_entrypoint(
            dummy_flow_1_entrypoint,
            __file__,
            cron=[
                "0 * * * *",
                "0 0 1 * *",
                "*/10 * * * *",
            ],
        )
        assert deployment.schedules
        assert deployment.schedules[0].schedule.cron == "0 * * * *"
        assert deployment.schedules[1].schedule.cron == "0 0 1 * *"
        assert deployment.schedules[2].schedule.cron == "*/10 * * * *"

    def test_from_entrypoint_accepts_rrule(self, dummy_flow_1_entrypoint):
        deployment = RunnerDeployment.from_entrypoint(
            dummy_flow_1_entrypoint, __file__, rrule="FREQ=MINUTELY"
        )
        assert deployment.schedules
        assert deployment.schedules[0].schedule.rrule == "FREQ=MINUTELY"

    def test_from_entrypoint_accepts_rrule_as_list(self, dummy_flow_1_entrypoint):
        deployment = RunnerDeployment.from_entrypoint(
            dummy_flow_1_entrypoint,
            __file__,
            rrule=[
                "FREQ=DAILY",
                "FREQ=WEEKLY",
                "FREQ=MONTHLY",
            ],
        )
        assert deployment.schedules
        assert deployment.schedules[0].schedule.rrule == "FREQ=DAILY"
        assert deployment.schedules[1].schedule.rrule == "FREQ=WEEKLY"
        assert deployment.schedules[2].schedule.rrule == "FREQ=MONTHLY"

    def test_from_entrypoint_accepts_schedules(self, dummy_flow_1_entrypoint):
        deployment = RunnerDeployment.from_entrypoint(
            dummy_flow_1_entrypoint,
            __file__,
            schedules=[
                DeploymentScheduleCreate(
                    schedule=CronSchedule(cron="* * * * *"), active=True
                ),
                IntervalSchedule(interval=datetime.timedelta(days=1)),
                {
                    "schedule": IntervalSchedule(interval=datetime.timedelta(days=2)),
                    "active": False,
                },
            ],
        )
        assert deployment.schedules
        assert deployment.schedules[0].schedule.cron == "* * * * *"
        assert deployment.schedules[0].active is True
        assert deployment.schedules[1].schedule.interval == datetime.timedelta(days=1)
        assert deployment.schedules[1].active is True
        assert deployment.schedules[2].schedule.interval == datetime.timedelta(days=2)
        assert deployment.schedules[2].active is False

    async def test_from_entrypoint_accepts_concurrency_limit_config(
        self, dummy_flow_1_entrypoint
    ):
        concurrency_limit_config = ConcurrencyLimitConfig(
            limit=42, collision_strategy="CANCEL_NEW"
        )
        deployment = RunnerDeployment.from_entrypoint(
            dummy_flow_1_entrypoint,
            __file__,
            concurrency_limit=concurrency_limit_config,
        )
        assert deployment.concurrency_limit == concurrency_limit_config.limit
        assert (
            deployment.concurrency_options.collision_strategy
            == concurrency_limit_config.collision_strategy
        )

    @pytest.mark.parametrize(
        "value,expected",
        [(True, True), (False, False), (None, False)],
    )
    def test_from_entrypoint_accepts_paused(
        self, value, expected, dummy_flow_1_entrypoint
    ):
        deployment = RunnerDeployment.from_entrypoint(
            dummy_flow_1_entrypoint, __file__, paused=value
        )

        assert deployment.paused is expected

    @pytest.mark.parametrize(
        "kwargs",
        [
            {**d1, **d2}
            for d1, d2 in combinations(
                [
                    {"interval": 3600},
                    {"cron": "* * * * *"},
                    {"rrule": "FREQ=MINUTELY"},
                    {
                        "schedules": [
                            DeploymentScheduleCreate(
                                schedule=CronSchedule(cron="* * * * *"), active=True
                            )
                        ]
                    },
                ],
                2,
            )
        ],
    )
    def test_from_entrypoint_raises_on_multiple_schedule_parameters(
        self, dummy_flow_1_entrypoint, kwargs
    ):
        expected_message = (
            "Only one of interval, cron, rrule, schedule, or schedules can be provided."
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
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1, __file__, interval=3600, version_type=VersionType.SIMPLE
        )

        deployment_id = await deployment.apply()

        deployment = await prefect_client.read_deployment(deployment_id)

        assert deployment.name == "test_runner"
        assert deployment.entrypoint == "tests/runner/test_runner.py:dummy_flow_1"
        assert deployment.version == "test"
        assert deployment.description == "I'm just here for tests"
        assert deployment.schedules[0].schedule.interval == datetime.timedelta(
            seconds=3600
        )
        assert deployment.work_pool_name is None
        assert deployment.work_queue_name is None
        assert deployment.path == "."
        assert deployment.enforce_parameter_schema
        assert deployment.job_variables == {}
        assert deployment.paused is False
        assert deployment.global_concurrency_limit is None

    async def test_apply_with_work_pool(
        self, prefect_client: PrefectClient, work_pool, process_work_pool
    ):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1,
            __file__,
            interval=3600,
        )

        deployment_id = await deployment.apply(
            work_pool_name=work_pool.name, image="my-repo/my-image:latest"
        )

        deployment = await prefect_client.read_deployment(deployment_id)

        assert deployment.work_pool_name == work_pool.name
        assert deployment.job_variables == {
            "image": "my-repo/my-image:latest",
        }
        assert deployment.work_queue_name == "default"

        # should result in the same deployment ID
        deployment2 = RunnerDeployment.from_flow(
            dummy_flow_1,
            __file__,
            interval=3600,
        )

        deployment_id = await deployment2.apply(work_pool_name=process_work_pool.name)
        deployment2 = await prefect_client.read_deployment(deployment_id)

        assert deployment2.work_pool_name == process_work_pool.name

        # this may look weird with a process pool but update's job isn't to enforce that schema
        assert deployment2.job_variables == {
            "image": "my-repo/my-image:latest",
        }
        assert deployment2.work_queue_name == "default"

    async def test_apply_with_image(self, prefect_client: PrefectClient, work_pool):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1,
            "test-image",
        )

        deployment_id = await deployment.apply(
            work_pool_name=work_pool.name, image="my-repo/my-image:latest"
        )

        deployment = await prefect_client.read_deployment(deployment_id)

        assert deployment.work_pool_name == work_pool.name
        assert deployment.job_variables == {
            "image": "my-repo/my-image:latest",
        }
        assert deployment.work_queue_name == "default"

        # should result in the same deployment ID
        deployment2 = RunnerDeployment.from_flow(
            dummy_flow_1,
            "test-image",
        )

        deployment_id = await deployment2.apply(image="my-other-repo/my-image:latest")
        deployment2 = await prefect_client.read_deployment(deployment_id)

        assert deployment2.work_pool_name == work_pool.name
        assert deployment2.job_variables == {
            "image": "my-other-repo/my-image:latest",
        }
        assert deployment2.work_queue_name == "default"

    async def test_apply_paused(self, prefect_client: PrefectClient):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1, __file__, interval=3600, paused=True
        )

        deployment_id = await deployment.apply()

        deployment = await prefect_client.read_deployment(deployment_id)

        assert deployment.paused is True

    @pytest.mark.parametrize(
        "from_flow_kwargs, apply_kwargs, expected_message",
        [
            (
                {"work_queue_name": "my-queue"},
                {},
                (
                    "A work queue can only be provided when registering a deployment"
                    " with a work pool."
                ),
            ),
            (
                {"job_variables": {"foo": "bar"}},
                {},
                (
                    "Job variables can only be provided when registering a deployment"
                    " with a work pool."
                ),
            ),
            (
                {},
                {"image": "my-repo/my-image:latest"},
                (
                    "An image can only be provided when registering a deployment with a"
                    " work pool."
                ),
            ),
        ],
    )
    async def test_apply_no_work_pool_failures(
        self, from_flow_kwargs, apply_kwargs, expected_message
    ):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1,
            __file__,
            interval=3600,
            **from_flow_kwargs,
        )

        with pytest.raises(
            ValueError,
            match=expected_message,
        ):
            await deployment.apply(**apply_kwargs)

    async def test_apply_raises_on_api_errors(self, work_pool_with_image_variable):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1,
            __file__,
            work_pool_name=work_pool_with_image_variable.name,
            job_variables={"image_pull_policy": "blork"},
        )

        with pytest.raises(
            DeploymentApplyError,
            match=re.escape(
                "Error creating deployment: Validation failed for field 'image_pull_policy'. Failure reason: 'blork' is not one of"
                " ['IfNotPresent', 'Always', 'Never']"
            ),
        ):
            await deployment.apply()

    def test_create_runner_deployment_from_storage(self, temp_storage: MockStorage):
        concurrency_limit_config = ConcurrencyLimitConfig(
            limit=42, collision_strategy="CANCEL_NEW"
        )
        deployment = RunnerDeployment.from_storage(
            storage=temp_storage,
            entrypoint="flows.py:test_flow",
            name="test-deployment",
            interval=datetime.timedelta(seconds=30),
            description="Test Deployment Description",
            tags=["tag1", "tag2"],
            version="1.0.0",
            version_type=VersionType.SIMPLE,
            enforce_parameter_schema=True,
            concurrency_limit=concurrency_limit_config,
        )
        assert isinstance(deployment, RunnerDeployment)

        # Verify the created RunnerDeployment's attributes
        assert deployment.name == "test-deployment"
        assert deployment.flow_name == "test-flow"
        assert deployment.schedules
        assert deployment.schedules[0].schedule.interval == datetime.timedelta(
            seconds=30
        )
        assert deployment.tags == ["tag1", "tag2"]
        assert deployment.version == "1.0.0"
        assert deployment.version_type == VersionType.SIMPLE
        assert deployment.description == "Test Deployment Description"
        assert deployment.enforce_parameter_schema is True
        assert deployment.concurrency_limit == concurrency_limit_config.limit
        assert (
            deployment.concurrency_options.collision_strategy
            == concurrency_limit_config.collision_strategy
        )
        assert deployment._path
        assert "$STORAGE_BASE_PATH" in deployment._path
        assert deployment.entrypoint == "flows.py:test_flow"
        assert deployment.storage == temp_storage

    async def test_create_runner_deployment_from_storage_async(
        self, temp_storage: MockStorage
    ):
        concurrency_limit_config = ConcurrencyLimitConfig(
            limit=42, collision_strategy="CANCEL_NEW"
        )
        deployment = await RunnerDeployment.afrom_storage(
            storage=temp_storage,
            entrypoint="flows.py:test_flow",
            name="test-deployment",
            interval=datetime.timedelta(seconds=30),
            description="Test Deployment Description",
            tags=["tag1", "tag2"],
            version="1.0.0",
            version_type=VersionType.SIMPLE,
            enforce_parameter_schema=True,
            concurrency_limit=concurrency_limit_config,
        )

        # Verify the created RunnerDeployment's attributes
        assert deployment.name == "test-deployment"
        assert deployment.flow_name == "test-flow"
        assert deployment.schedules
        assert deployment.schedules[0].schedule.interval == datetime.timedelta(
            seconds=30
        )
        assert deployment.tags == ["tag1", "tag2"]
        assert deployment.version == "1.0.0"
        assert deployment.version_type == VersionType.SIMPLE
        assert deployment.description == "Test Deployment Description"
        assert deployment.enforce_parameter_schema is True
        assert deployment.concurrency_limit == concurrency_limit_config.limit
        assert (
            deployment.concurrency_options.collision_strategy
            == concurrency_limit_config.collision_strategy
        )
        assert deployment._path
        assert "$STORAGE_BASE_PATH" in deployment._path
        assert deployment.entrypoint == "flows.py:test_flow"
        assert deployment.storage == temp_storage

    def test_from_storage_accepts_schedules(self, temp_storage: MockStorage):
        deployment = RunnerDeployment.from_storage(
            storage=temp_storage,
            entrypoint="flows.py:test_flow",
            name="test-deployment",
            schedules=[
                DeploymentScheduleCreate(
                    schedule=CronSchedule(cron="* * * * *"), active=True
                ),
                IntervalSchedule(interval=datetime.timedelta(days=1)),
                {
                    "schedule": IntervalSchedule(interval=datetime.timedelta(days=2)),
                    "active": False,
                },
                Interval(datetime.timedelta(days=3)),
            ],
        )
        assert isinstance(deployment, RunnerDeployment)
        assert deployment.schedules
        assert deployment.schedules[0].schedule.cron == "* * * * *"
        assert deployment.schedules[0].active is True
        assert deployment.schedules[1].schedule.interval == datetime.timedelta(days=1)
        assert deployment.schedules[1].active is True
        assert deployment.schedules[2].schedule.interval == datetime.timedelta(days=2)
        assert deployment.schedules[2].active is False
        assert deployment.schedules[3].schedule.interval == datetime.timedelta(days=3)
        assert deployment.schedules[3].active is True

    async def test_afrom_storage_accepts_schedules(self, temp_storage: MockStorage):
        deployment = await RunnerDeployment.afrom_storage(
            storage=temp_storage,
            entrypoint="flows.py:test_flow",
            name="test-deployment",
            schedules=[
                DeploymentScheduleCreate(
                    schedule=CronSchedule(cron="* * * * *"), active=True
                ),
                IntervalSchedule(interval=datetime.timedelta(days=1)),
                {
                    "schedule": IntervalSchedule(interval=datetime.timedelta(days=2)),
                    "active": False,
                },
                Interval(datetime.timedelta(days=3)),
            ],
        )
        assert deployment.schedules
        assert deployment.schedules[0].schedule.cron == "* * * * *"
        assert deployment.schedules[0].active is True
        assert deployment.schedules[1].schedule.interval == datetime.timedelta(days=1)
        assert deployment.schedules[1].active is True
        assert deployment.schedules[2].schedule.interval == datetime.timedelta(days=2)
        assert deployment.schedules[2].active is False
        assert deployment.schedules[3].schedule.interval == datetime.timedelta(days=3)
        assert deployment.schedules[3].active is True

    @pytest.mark.parametrize(
        "value,expected",
        [(True, True), (False, False), (None, False)],
    )
    def test_from_storage_accepts_paused(
        self, value: Union[bool, None], expected: bool, temp_storage: MockStorage
    ):
        deployment = RunnerDeployment.from_storage(
            storage=temp_storage,
            entrypoint="flows.py:test_flow",
            name="test-deployment",
            paused=value,
        )
        assert isinstance(deployment, RunnerDeployment)

        assert deployment.paused is expected

    @pytest.mark.parametrize(
        "value,expected",
        [(True, True), (False, False), (None, False)],
    )
    async def test_afrom_storage_accepts_paused(
        self, value: Union[bool, None], expected: bool, temp_storage: MockStorage
    ):
        deployment = await RunnerDeployment.afrom_storage(
            storage=temp_storage,
            entrypoint="flows.py:test_flow",
            name="test-deployment",
            paused=value,
        )

        assert deployment.paused is expected

    async def test_init_runner_deployment_with_schedules(self):
        schedule = CronSchedule(cron="* * * * *")

        deployment = RunnerDeployment(
            flow=dummy_flow_1,
            name="test-deployment",
            schedules=[schedule],
        )

        assert deployment.schedules
        assert deployment.schedules[0].schedule.cron == "* * * * *"
        assert deployment.schedules[0].active is True

    async def test_init_runner_deployment_with_invalid_schedules(self):
        with pytest.raises(ValueError, match="Invalid schedule"):
            RunnerDeployment(
                flow=dummy_flow_1,
                name="test-deployment",
                schedules=[
                    "not a schedule",
                ],
            )

    async def test_deployment_name_with_dots(self):
        # regression test for https://github.com/PrefectHQ/prefect/issues/16551
        deployment = RunnerDeployment.from_flow(dummy_flow_1, name="..test-deployment")
        assert deployment.name == "..test-deployment"

        deployment2 = RunnerDeployment.from_flow(
            dummy_flow_1, name="flow-from-my.python.module"
        )
        assert deployment2.name == "flow-from-my.python.module"

    async def test_from_flow_with_frozen_parameters(
        self, prefect_client: PrefectClient
    ):
        """Test that frozen parameters are properly handled in deployment creation."""

        @flow
        def dummy_flow_4(value: Any): ...

        deployment_object = RunnerDeployment.from_flow(
            dummy_flow_4,
            __file__,
            parameters={"value": freeze("test")},
        )
        assert deployment_object.parameters == {"value": "test"}
        deployment_id = await deployment_object.apply()

        deployment = await prefect_client.read_deployment(deployment_id)

        assert deployment.parameters == {"value": "test"}
        assert (
            deployment.parameter_openapi_schema["properties"]["value"]["readOnly"]
            is True
        )
        assert deployment.parameter_openapi_schema["properties"]["value"]["enum"] == [
            "test"
        ]

    async def test_from_flow_with_frozen_parameters_preserves_type(
        self, prefect_client: PrefectClient
    ):
        """Test that frozen parameters preserve their type information."""

        @flow
        def dummy_flow_5(number: int): ...

        deployment_object = RunnerDeployment.from_flow(
            dummy_flow_5,
            __file__,
            parameters={"number": freeze(42)},
        )
        assert deployment_object.parameters == {"number": 42}

        deployment_id = await deployment_object.apply()

        deployment = await prefect_client.read_deployment(deployment_id)

        assert deployment.parameters == {"number": 42}
        assert (
            deployment.parameter_openapi_schema["properties"]["number"]["type"]
            == "integer"
        )
        assert (
            deployment.parameter_openapi_schema["properties"]["number"]["readOnly"]
            is True
        )
        assert deployment.parameter_openapi_schema["properties"]["number"]["enum"] == [
            42
        ]


class TestServer:
    async def test_healthcheck_fails_as_expected(self):
        runner = Runner()
        runner.last_polled = now("UTC") - datetime.timedelta(minutes=5)

        health_check = perform_health_check(runner)
        assert health_check().status_code == status.HTTP_503_SERVICE_UNAVAILABLE

        runner.last_polled = now("UTC")
        assert health_check().status_code == status.HTTP_200_OK

    @pytest.mark.skip("This test is flaky and needs to be fixed")
    @pytest.mark.parametrize("enabled", [True, False])
    async def test_webserver_start_flag(self, enabled: bool):
        with temporary_settings(updates={PREFECT_RUNNER_SERVER_ENABLE: enabled}):
            with mock.patch("prefect.runner.runner.threading.Thread") as mocked_thread:
                runner = Runner()
                await runner.start(run_once=True)

            if enabled:
                mocked_thread.assert_called_once()
                mocked_thread.return_value.start.assert_called_once()
            if not enabled:
                mocked_thread.assert_not_called()
                mocked_thread.return_value.start.assert_not_called()


class TestDeploy:
    @pytest.fixture
    def mock_build_image(self, monkeypatch):
        mock = MagicMock()

        monkeypatch.setattr("prefect.docker.docker_image.build_image", mock)
        return mock

    @pytest.fixture
    def mock_docker_client(self, monkeypatch):
        mock = MagicMock()
        mock.return_value.__enter__.return_value = mock
        mock.api.push.return_value = []
        monkeypatch.setattr("prefect.docker.docker_image.docker_client", mock)
        return mock

    @pytest.fixture
    def mock_generate_default_dockerfile(self, monkeypatch):
        mock = MagicMock()
        monkeypatch.setattr(
            "prefect.docker.docker_image.generate_default_dockerfile", mock
        )
        return mock

    async def test_deploy(
        self,
        mock_build_image,
        mock_docker_client,
        mock_generate_default_dockerfile,
        work_pool_with_image_variable,
        prefect_client: PrefectClient,
        capsys,
        temp_storage: MockStorage,
    ):
        deployment_ids = await deploy(
            await dummy_flow_1.to_deployment(
                __file__,
                schedule=Interval(
                    3600,
                    parameters={"number": 42},
                    slug="test-slug",
                ),
            ),
            await (
                await flow.from_source(
                    source=temp_storage, entrypoint="flows.py:test_flow"
                )
            ).to_deployment(
                __file__,
                schedule=Interval(
                    3600,
                    parameters={"number": 42},
                    slug="test-slug",
                ),
            ),
            work_pool_name=work_pool_with_image_variable.name,
            image=DockerImage(
                name="test-registry/test-image",
                tag="test-tag",
            ),
        )
        assert len(deployment_ids) == 2
        mock_generate_default_dockerfile.assert_called_once()
        mock_build_image.assert_called_once_with(
            tag="test-registry/test-image:test-tag", context=Path.cwd(), pull=True
        )
        mock_docker_client.api.push.assert_called_once_with(
            repository="test-registry/test-image",
            tag="test-tag",
            stream=True,
            decode=True,
        )

        deployment_1 = await prefect_client.read_deployment_by_name(
            f"{dummy_flow_1.name}/test_runner"
        )
        assert deployment_1.id == deployment_ids[0]
        assert len(deployment_1.schedules) == 1
        assert isinstance(deployment_1.schedules[0].schedule, IntervalSchedule)
        assert deployment_1.schedules[0].schedule.interval == datetime.timedelta(
            seconds=3600
        )
        assert deployment_1.schedules[0].parameters == {"number": 42}
        assert deployment_1.schedules[0].slug == "test-slug"

        deployment_2 = await prefect_client.read_deployment_by_name(
            "test-flow/test_runner"
        )
        assert deployment_2.id == deployment_ids[1]
        assert deployment_2.pull_steps == [{"prefect.fake.module": {}}]
        assert len(deployment_2.schedules) == 1
        assert isinstance(deployment_2.schedules[0].schedule, IntervalSchedule)
        assert deployment_2.schedules[0].schedule.interval == datetime.timedelta(
            seconds=3600
        )
        assert deployment_2.schedules[0].parameters == {"number": 42}
        assert deployment_2.schedules[0].slug == "test-slug"

        console_output = capsys.readouterr().out
        assert "prefect worker start --pool" in console_output
        assert work_pool_with_image_variable.name in console_output
        assert "prefect deployment run [DEPLOYMENT_NAME]" in console_output

    async def test_deploy_to_default_work_pool(
        self,
        mock_build_image,
        mock_docker_client,
        mock_generate_default_dockerfile,
        work_pool_with_image_variable,
        prefect_client: PrefectClient,
        capsys,
        temp_storage: MockStorage,
    ):
        with temporary_settings(
            updates={PREFECT_DEFAULT_WORK_POOL_NAME: work_pool_with_image_variable.name}
        ):
            deployment_ids = await deploy(
                await dummy_flow_1.to_deployment(__file__),
                await (
                    await flow.from_source(
                        source=temp_storage, entrypoint="flows.py:test_flow"
                    )
                ).to_deployment(__file__),
                image=DockerImage(
                    name="test-registry/test-image",
                    tag="test-tag",
                ),
            )
            assert len(deployment_ids) == 2
            mock_generate_default_dockerfile.assert_called_once()
            mock_build_image.assert_called_once_with(
                tag="test-registry/test-image:test-tag", context=Path.cwd(), pull=True
            )
            mock_docker_client.api.push.assert_called_once_with(
                repository="test-registry/test-image",
                tag="test-tag",
                stream=True,
                decode=True,
            )

            deployment_1 = await prefect_client.read_deployment_by_name(
                f"{dummy_flow_1.name}/test_runner"
            )
            assert deployment_1.id == deployment_ids[0]

            deployment_2 = await prefect_client.read_deployment_by_name(
                "test-flow/test_runner"
            )
            assert deployment_2.id == deployment_ids[1]
            assert deployment_2.pull_steps == [{"prefect.fake.module": {}}]

            console_output = capsys.readouterr().out
            assert "prefect worker start --pool" in console_output
            assert work_pool_with_image_variable.name in console_output
            assert "prefect deployment run [DEPLOYMENT_NAME]" in console_output

    async def test_deploy_with_active_workers(
        self,
        mock_build_image,
        mock_docker_client,
        mock_generate_default_dockerfile,
        work_pool_with_image_variable,
        prefect_client: PrefectClient,
        capsys,
        temp_storage: MockStorage,
        monkeypatch,
    ):
        mock_read_workers_for_work_pool = AsyncMock(
            return_value=[
                Worker(
                    name="test-worker",
                    work_pool_id=work_pool_with_image_variable.id,
                    status=WorkerStatus.ONLINE,
                )
            ]
        )
        monkeypatch.setattr(
            "prefect.client.orchestration.PrefectClient.read_workers_for_work_pool",
            mock_read_workers_for_work_pool,
        )
        deployment_ids = await deploy(
            await dummy_flow_1.to_deployment(__file__),
            await (
                await flow.from_source(
                    source=temp_storage, entrypoint="flows.py:test_flow"
                )
            ).to_deployment(__file__),
            work_pool_name=work_pool_with_image_variable.name,
            image=DockerImage(
                name="test-registry/test-image",
                tag="test-tag",
            ),
        )
        assert len(deployment_ids) == 2
        mock_generate_default_dockerfile.assert_called_once()
        mock_build_image.assert_called_once_with(
            tag="test-registry/test-image:test-tag", context=Path.cwd(), pull=True
        )
        mock_docker_client.api.push.assert_called_once_with(
            repository="test-registry/test-image",
            tag="test-tag",
            stream=True,
            decode=True,
        )

        deployment_1 = await prefect_client.read_deployment_by_name(
            f"{dummy_flow_1.name}/test_runner"
        )
        assert deployment_1.id == deployment_ids[0]

        deployment_2 = await prefect_client.read_deployment_by_name(
            "test-flow/test_runner"
        )
        assert deployment_2.id == deployment_ids[1]
        assert deployment_2.pull_steps == [{"prefect.fake.module": {}}]

        console_output = capsys.readouterr().out
        assert (
            f"prefect worker start --pool {work_pool_with_image_variable.name!r}"
            not in console_output
        )
        assert "prefect deployment run [DEPLOYMENT_NAME]" in console_output

    async def test_deploy_non_existent_work_pool(self):
        with pytest.raises(
            ValueError, match="Could not find work pool 'non-existent'."
        ):
            await deploy(
                await dummy_flow_1.to_deployment(__file__),
                work_pool_name="non-existent",
                image="test-registry/test-image",
            )

    async def test_deploy_non_image_work_pool(self, process_work_pool):
        with pytest.raises(
            ValueError,
            match=(
                f"Work pool {process_work_pool.name!r} does not support custom Docker"
                " images."
            ),
        ):
            await deploy(
                await dummy_flow_1.to_deployment(__file__),
                work_pool_name=process_work_pool.name,
                image="test-registry/test-image",
            )

    async def test_deployment_image_tag_handling(self):
        # test image tag has default
        image = DockerImage(
            name="test-registry/test-image",
        )
        assert image.name == "test-registry/test-image"
        assert image.tag.startswith(str(now("UTC").year))

        # test image tag can be inferred
        image = DockerImage(
            name="test-registry/test-image:test-tag",
        )
        assert image.name == "test-registry/test-image"
        assert image.tag == "test-tag"
        assert image.reference == "test-registry/test-image:test-tag"

        # test image tag can be provided
        image = DockerImage(name="test-registry/test-image", tag="test-tag")
        assert image.name == "test-registry/test-image"
        assert image.tag == "test-tag"
        assert image.reference == "test-registry/test-image:test-tag"

        # test both can't be provided
        with pytest.raises(
            ValueError, match="both 'test-tag' and 'bad-tag' were provided"
        ):
            DockerImage(name="test-registry/test-image:test-tag", tag="bad-tag")

    async def test_deploy_custom_dockerfile(
        self,
        mock_build_image,
        mock_docker_client,
        mock_generate_default_dockerfile,
        work_pool_with_image_variable,
    ):
        deployment_ids = await deploy(
            await dummy_flow_1.to_deployment(__file__),
            await dummy_flow_2.to_deployment(__file__),
            work_pool_name=work_pool_with_image_variable.name,
            image=DockerImage(
                name="test-registry/test-image",
                tag="test-tag",
                dockerfile="Dockerfile",
            ),
        )
        assert len(deployment_ids) == 2
        # Shouldn't be called because we're providing a custom Dockerfile
        mock_generate_default_dockerfile.assert_not_called()
        mock_build_image.assert_called_once_with(
            tag="test-registry/test-image:test-tag",
            context=Path.cwd(),
            pull=True,
            dockerfile="Dockerfile",
        )

    async def test_deploy_skip_build(
        self,
        mock_build_image,
        mock_docker_client,
        mock_generate_default_dockerfile,
        work_pool_with_image_variable,
        prefect_client: PrefectClient,
    ):
        deployment_ids = await deploy(
            await dummy_flow_1.to_deployment(__file__),
            await dummy_flow_2.to_deployment(__file__),
            work_pool_name=work_pool_with_image_variable.name,
            image=DockerImage(
                name="test-registry/test-image",
                tag="test-tag",
            ),
            build=False,
        )
        assert len(deployment_ids) == 2
        mock_generate_default_dockerfile.assert_not_called()
        mock_build_image.assert_not_called()
        mock_docker_client.api.push.assert_not_called()

        deployment_1 = await prefect_client.read_deployment(
            deployment_id=deployment_ids[0]
        )
        assert (
            deployment_1.job_variables["image"] == "test-registry/test-image:test-tag"
        )

        deployment_2 = await prefect_client.read_deployment(
            deployment_id=deployment_ids[1]
        )
        assert (
            deployment_2.job_variables["image"] == "test-registry/test-image:test-tag"
        )

    async def test_deploy_skip_push(
        self,
        mock_build_image,
        mock_docker_client,
        mock_generate_default_dockerfile,
        work_pool_with_image_variable,
    ):
        deployment_ids = await deploy(
            await dummy_flow_1.to_deployment(__file__),
            await dummy_flow_2.to_deployment(__file__),
            work_pool_name=work_pool_with_image_variable.name,
            image=DockerImage(
                name="test-registry/test-image",
                tag="test-tag",
            ),
            push=False,
        )
        assert len(deployment_ids) == 2
        mock_generate_default_dockerfile.assert_called_once()
        mock_build_image.assert_called_once_with(
            tag="test-registry/test-image:test-tag", context=Path.cwd(), pull=True
        )
        mock_docker_client.api.push.assert_not_called()

    async def test_deploy_do_not_print_next_steps(
        self,
        mock_build_image,
        mock_docker_client,
        mock_generate_default_dockerfile,
        work_pool_with_image_variable,
        capsys,
        temp_storage: MockStorage,
    ):
        deployment_ids = await deploy(
            await dummy_flow_1.to_deployment(__file__),
            await (
                await flow.from_source(
                    source=temp_storage, entrypoint="flows.py:test_flow"
                )
            ).to_deployment(__file__),
            work_pool_name=work_pool_with_image_variable.name,
            image=DockerImage(
                name="test-registry/test-image",
                tag="test-tag",
            ),
            print_next_steps_message=False,
        )
        assert len(deployment_ids) == 2

        assert "prefect deployment run [DEPLOYMENT_NAME]" not in capsys.readouterr().out

    async def test_deploy_push_work_pool(
        self,
        mock_build_image,
        mock_docker_client,
        mock_generate_default_dockerfile,
        push_work_pool,
        capsys,
        temp_storage: MockStorage,
    ):
        deployment_ids = await deploy(
            await dummy_flow_1.to_deployment(__file__),
            await (
                await flow.from_source(
                    source=temp_storage, entrypoint="flows.py:test_flow"
                )
            ).to_deployment(__file__),
            work_pool_name=push_work_pool.name,
            image=DockerImage(
                name="test-registry/test-image",
                tag="test-tag",
            ),
            print_next_steps_message=False,
        )
        assert len(deployment_ids) == 2

        console_output = capsys.readouterr().out
        assert "prefect worker start" not in console_output
        assert "prefect deployment run [DEPLOYMENT_NAME]" not in console_output

    async def test_deploy_managed_work_pool_doesnt_prompt_worker_start_or_build_image(
        self,
        managed_work_pool,
        capsys,
        mock_generate_default_dockerfile,
        mock_build_image,
        mock_docker_client,
        temp_storage: MockStorage,
    ):
        deployment_ids = await deploy(
            await dummy_flow_1.to_deployment(__file__),
            await (
                await flow.from_source(
                    source=temp_storage, entrypoint="flows.py:test_flow"
                )
            ).to_deployment(__file__),
            work_pool_name=managed_work_pool.name,
            image=DockerImage(
                name="test-registry/test-image",
                tag="test-tag",
            ),
            print_next_steps_message=False,
        )

        assert len(deployment_ids) == 2

        console_output = capsys.readouterr().out
        assert "Successfully created/updated all deployments!" in console_output

        assert "Building image" not in capsys.readouterr().out
        assert "Pushing image" not in capsys.readouterr().out
        assert "prefect worker start" not in console_output
        assert "prefect deployment run [DEPLOYMENT_NAME]" not in console_output

        mock_generate_default_dockerfile.assert_not_called()
        mock_build_image.assert_not_called()
        mock_docker_client.api.push.assert_not_called()

    async def test_deploy_with_image_string(
        self,
        mock_build_image,
        mock_docker_client,
        mock_generate_default_dockerfile,
        work_pool_with_image_variable,
        temp_storage: MockStorage,
    ):
        deployment_ids = await deploy(
            await dummy_flow_1.to_deployment(__file__),
            await (
                await flow.from_source(
                    source=temp_storage, entrypoint="flows.py:test_flow"
                )
            ).to_deployment(__file__),
            work_pool_name=work_pool_with_image_variable.name,
            image="test-registry/test-image:test-tag",
        )
        assert len(deployment_ids) == 2

        mock_build_image.assert_called_once_with(
            tag="test-registry/test-image:test-tag",
            context=Path.cwd(),
            pull=True,
        )

    async def test_deploy_without_image_with_flow_stored_remotely(
        self,
        work_pool_with_image_variable,
        temp_storage: MockStorage,
    ):
        deployment_id = await deploy(
            await (
                await flow.from_source(
                    source=temp_storage, entrypoint="flows.py:test_flow"
                )
            ).to_deployment(__file__),
            work_pool_name=work_pool_with_image_variable.name,
        )

        assert len(deployment_id) == 1

    async def test_deploy_without_image_or_flow_storage_raises(
        self,
        work_pool_with_image_variable,
    ):
        with pytest.raises(ValueError):
            await deploy(
                await dummy_flow_1.to_deployment(__file__),
                work_pool_name=work_pool_with_image_variable.name,
            )

    async def test_deploy_with_image_and_flow_stored_remotely_raises(
        self,
        work_pool_with_image_variable,
        temp_storage: MockStorage,
    ):
        with pytest.raises(RuntimeError, match="Failed to generate Dockerfile"):
            await deploy(
                await (
                    await flow.from_source(
                        source=temp_storage, entrypoint="flows.py:test_flow"
                    )
                ).to_deployment(__file__),
                work_pool_name=work_pool_with_image_variable.name,
                image="test-registry/test-image:test-tag",
            )

    async def test_deploy_multiple_flows_one_using_storage_one_without_raises_with_no_image(
        self, work_pool_with_image_variable, temp_storage: MockStorage
    ):
        with pytest.raises(ValueError):
            await deploy(
                await dummy_flow_1.to_deployment(__file__),
                await (
                    await flow.from_source(
                        source=temp_storage, entrypoint="flows.py:test_flow"
                    )
                ).to_deployment(__file__),
                work_pool_name=work_pool_with_image_variable.name,
            )

    async def test_deploy_with_module_path_entrypoint(
        self, work_pool_with_image_variable, prefect_client
    ):
        deployment_ids = await deploy(
            await dummy_flow_1.to_deployment(
                __file__, entrypoint_type=EntrypointType.MODULE_PATH
            ),
            work_pool_name=work_pool_with_image_variable.name,
        )
        assert len(deployment_ids) == 1

        deployment = await prefect_client.read_deployment(deployment_ids[0])
        assert deployment.entrypoint == "test_runner.dummy_flow_1"

    async def test_deploy_with_image_string_no_tag(
        self,
        mock_build_image: MagicMock,
        mock_docker_client,
        mock_generate_default_dockerfile,
        work_pool_with_image_variable,
        temp_storage: MockStorage,
    ):
        deployment_ids = await deploy(
            await dummy_flow_1.to_deployment(__file__),
            await (
                await flow.from_source(
                    source=temp_storage, entrypoint="flows.py:test_flow"
                )
            ).to_deployment(__file__),
            work_pool_name=work_pool_with_image_variable.name,
            image="test-registry/test-image",
        )
        assert len(deployment_ids) == 2

        used_name, used_tag = parse_image_tag(
            mock_build_image.mock_calls[0].kwargs["tag"]
        )
        assert used_name == "test-registry/test-image"
        assert used_tag is not None

    async def test_deploy_with_partial_success(
        self,
        mock_build_image,
        mock_docker_client,
        mock_generate_default_dockerfile,
        work_pool_with_image_variable,
        capsys,
        temp_storage: MockStorage,
    ):
        deployment_ids = await deploy(
            await dummy_flow_1.to_deployment(
                __file__, job_variables={"image_pull_policy": "blork"}
            ),
            await (
                await flow.from_source(
                    source=temp_storage, entrypoint="flows.py:test_flow"
                )
            ).to_deployment(__file__),
            work_pool_name=work_pool_with_image_variable.name,
            image="test-registry/test-image",
        )
        assert len(deployment_ids) == 1

        console_output = capsys.readouterr().out
        assert (
            "Encountered errors while creating/updating deployments" in console_output
        )
        assert "failed" in console_output
        # just the start of the error due to wrapping
        assert "'blork' is not one" in console_output
        assert "prefect worker start" in console_output
        assert "To execute flow runs from these deployments" in console_output

    async def test_deploy_with_complete_failure(
        self,
        mock_build_image,
        mock_docker_client,
        mock_generate_default_dockerfile,
        work_pool_with_image_variable,
        capsys,
        temp_storage: MockStorage,
    ):
        deployment_ids = await deploy(
            await dummy_flow_1.to_deployment(
                __file__, job_variables={"image_pull_policy": "blork"}
            ),
            await (
                await flow.from_source(
                    source=temp_storage, entrypoint="flows.py:test_flow"
                )
            ).to_deployment(__file__, job_variables={"image_pull_policy": "blork"}),
            work_pool_name=work_pool_with_image_variable.name,
            image="test-registry/test-image",
        )
        assert len(deployment_ids) == 0

        console_output = capsys.readouterr().out
        assert (
            "Encountered errors while creating/updating deployments" in console_output
        )
        assert "failed" in console_output
        # just the start of the error due to wrapping
        assert "'blork' is not one" in console_output

        assert "prefect worker start" not in console_output
        assert "To execute flow runs from these deployments" not in console_output

    async def test_deploy_raises_with_only_deployment_failed(
        self,
        mock_build_image,
        mock_docker_client,
        mock_generate_default_dockerfile,
        work_pool_with_image_variable,
        capsys,
    ):
        with pytest.raises(
            DeploymentApplyError,
            match=re.escape(
                "Error creating deployment: Validation failed for field 'image_pull_policy'. Failure reason: 'blork' is not one of"
                " ['IfNotPresent', 'Always', 'Never']"
            ),
        ):
            await deploy(
                await dummy_flow_1.to_deployment(
                    __file__, job_variables={"image_pull_policy": "blork"}
                ),
                work_pool_name=work_pool_with_image_variable.name,
                image="test-registry/test-image",
            )

    async def test_deploy_raises_helpful_error_when_process_pool_has_no_image(
        self,
        process_work_pool,
    ):
        with pytest.raises(
            ValueError,
            match="If you are attempting to deploy a flow to a local process work pool",
        ):
            await deploy(
                await dummy_flow_1.to_deployment(__file__),
                work_pool_name=process_work_pool.name,
                image="test-registry/test-image",
            )

    async def test_deploy_to_process_work_pool_with_no_storage(self, process_work_pool):
        with pytest.raises(
            ValueError,
            match="Either an image or remote storage location must be provided when deploying"
            " a deployment.",
        ):
            await deploy(
                await dummy_flow_1.to_deployment(__file__),
                work_pool_name=process_work_pool.name,
            )

    @pytest.mark.parametrize("ignore_warnings", [True, False])
    async def test_deploy_to_process_work_pool_with_storage(
        self, process_work_pool, capsys, ignore_warnings, temp_storage: MockStorage
    ):
        deployment_ids = await deploy(
            await (
                await flow.from_source(
                    source=temp_storage, entrypoint="flows.py:test_flow"
                )
            ).to_deployment(__file__),
            work_pool_name=process_work_pool.name,
            ignore_warnings=ignore_warnings,
        )
        assert len(deployment_ids) == 1
        console_output = capsys.readouterr().out
        if ignore_warnings:
            assert (
                "Looks like you're deploying to a process work pool."
                not in console_output
            )
        else:
            assert (
                "Looks like you're deploying to a process work pool." in console_output
            )

    async def test_deploy_with_triggers(
        self,
        mock_build_image,
        mock_docker_client,
        mock_generate_default_dockerfile,
        work_pool_with_image_variable,
        prefect_client: PrefectClient,
    ):
        deployment_ids = await deploy(
            await dummy_flow_1.to_deployment(
                __file__,
                triggers=[
                    DeploymentEventTrigger(
                        name="test-trigger",
                        enabled=True,
                        posture=Posture.Reactive,
                        match={"prefect.resource.id": "prefect.flow-run.*"},
                        expect=["prefect.flow-run.Completed"],
                    )
                ],
            ),
            work_pool_name=work_pool_with_image_variable.name,
            image="test-registry/test-image",
        )
        assert len(deployment_ids) == 1
        triggers = await prefect_client._client.get(
            f"/automations/related-to/prefect.deployment.{deployment_ids[0]}"
        )
        assert len(triggers.json()) == 1
        assert triggers.json()[0]["name"] == "test-trigger"

    async def test_deploy_with_triggers_and_update(
        self,
        mock_build_image,
        mock_docker_client,
        mock_generate_default_dockerfile,
        work_pool_with_image_variable,
        prefect_client: PrefectClient,
    ):
        deployment_ids = await deploy(
            await dummy_flow_1.to_deployment(
                __file__,
                triggers=[
                    DeploymentEventTrigger(
                        name="test-trigger",
                        enabled=True,
                        posture=Posture.Reactive,
                        match={"prefect.resource.id": "prefect.flow-run.*"},
                        expect=["prefect.flow-run.Completed"],
                    )
                ],
            ),
            work_pool_name=work_pool_with_image_variable.name,
            image="test-registry/test-image",
        )
        assert len(deployment_ids) == 1
        triggers = await prefect_client._client.get(
            f"/automations/related-to/prefect.deployment.{deployment_ids[0]}"
        )
        assert len(triggers.json()) == 1
        assert triggers.json()[0]["name"] == "test-trigger"
        assert triggers.json()[0]["enabled"]

        deployment_ids = await deploy(
            await dummy_flow_1.to_deployment(
                __file__,
                triggers=[
                    DeploymentEventTrigger(
                        name="test-trigger-2",
                        enabled=False,
                        posture=Posture.Reactive,
                        match={"prefect.resource.id": "prefect.flow-run.*"},
                        expect=["prefect.flow-run.Completed"],
                    )
                ],
            ),
            work_pool_name=work_pool_with_image_variable.name,
            image="test-registry/test-image",
        )
        assert len(deployment_ids) == 1
        triggers = await prefect_client._client.get(
            f"/automations/related-to/prefect.deployment.{deployment_ids[0]}"
        )
        assert len(triggers.json()) == 1
        assert triggers.json()[0]["name"] == "test-trigger-2"
        assert not triggers.json()[0]["enabled"]


class TestDockerImage:
    def test_adds_default_registry_url(self):
        with temporary_settings(
            {PREFECT_DEFAULT_DOCKER_BUILD_NAMESPACE: "alltheimages.com/my-org"}
        ):
            image = DockerImage(name="test-image")
            assert image.name == "alltheimages.com/my-org/test-image"

    def test_override_default_registry_url(self):
        with temporary_settings(
            {PREFECT_DEFAULT_DOCKER_BUILD_NAMESPACE: "alltheimages.com/my-org"}
        ):
            image = DockerImage(name="otherimages.com/my-org/test-image")
            assert image.name == "otherimages.com/my-org/test-image"

    def test_no_default_registry_url_by_default(self):
        image = DockerImage(name="my-org/test-image")
        assert image.name == "my-org/test-image"
