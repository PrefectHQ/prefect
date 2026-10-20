from __future__ import annotations

import asyncio
import datetime
import os
import re
import signal
import sys
import tempfile
import time
import uuid
import warnings
from itertools import combinations
from pathlib import Path
from textwrap import dedent
from time import sleep
from typing import Any, Coroutine, Generator, List, Union
from unittest import mock
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import anyio
import httpx
import pytest
import respx
from pydantic import BaseModel
from starlette import status

import prefect.runner
import prefect.runner._starter_direct as starter_mod
import prefect.types._datetime
from prefect import __version__, aserve, flow, serve, task
from prefect._internal.compatibility.deprecated import PrefectDeprecationWarning
from prefect._internal.server_maintenance import record_maintenance_backoff
from prefect._internal.versioning import VersionType
from prefect.blocks.core import BlockNotSavedError
from prefect.blocks.system import Secret
from prefect.cli.deploy._storage import _PullStepStorage
from prefect.client.orchestration import PrefectClient, SyncPrefectClient
from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.objects import (
    ConcurrencyLimitConfig,
    FlowRun,
    StateType,
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
from prefect.exceptions import PrefectHTTPStatusError
from prefect.flow_engine import (
    run_flow_in_subprocess as original_run_flow_in_subprocess,
)
from prefect.flows import Flow
from prefect.logging.loggers import flow_run_logger
from prefect.runner._process_manager import ProcessHandle
from prefect.runner.runner import Runner
from prefect.runner.server import perform_health_check, run_count
from prefect.schedules import Cron, Interval
from prefect.settings import (
    PREFECT_CLIENT_MAX_RETRIES,
    PREFECT_CLIENT_RETRY_JITTER_FACTOR,
    PREFECT_DEFAULT_DOCKER_BUILD_NAMESPACE,
    PREFECT_DEFAULT_WORK_POOL_NAME,
    PREFECT_RUNNER_POLL_FREQUENCY,
    PREFECT_RUNNER_PROCESS_LIMIT,
    PREFECT_RUNNER_SERVER_ENABLE,
    temporary_settings,
)
from prefect.types._datetime import now
from prefect.utilities import processutils
from prefect.utilities.annotations import freeze
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.dockerutils import parse_image_tag
from prefect.utilities.filesystem import tmpchdir
from prefect.utilities.slugify import slugify

pytestmark = pytest.mark.clear_db


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


class ClassWithInstanceMethod:
    def __init__(self, value: int):
        self.value = value

    @flow
    def instance_method_flow(self, x: int):
        return self.value + x


def instance_on_cancellation(flow, flow_run, state):
    logger = flow_run_logger(flow_run, flow)
    logger.info("Instance method flow was cancelled!")


class ClassWithCancellableFlow:
    @flow(on_cancellation=[instance_on_cancellation], log_prints=True)
    def cancellable_flow(self, sleep_time: int = 100):
        sleep(sleep_time)


def instance_on_crashed(flow, flow_run, state):
    logger = flow_run_logger(flow_run, flow)
    logger.info("Instance method flow crashed!")
    if marker_path := os.environ.get("PREFECT_TEST_INSTANCE_CRASH_HOOK_MARKER"):
        Path(marker_path).touch()


class ClassWithCrashingFlow:
    @flow(on_crashed=[instance_on_crashed], log_prints=True)
    def crashing_flow(self):
        print("Oh boy, here I go crashing again...")
        os.kill(os.getpid(), signal.SIGTERM)


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


class MockModuleStorage:
    """
    A mock storage class that writes a Python package structure for module path testing.
    """

    def __init__(self, base_path: Path):
        self._base_path = base_path

    def set_base_path(self, path: Path):
        self._base_path = path

    @property
    def destination(self):
        return self._base_path

    @property
    def pull_interval(self):
        return 60

    async def pull_code(self):
        if self._base_path:
            pkg_dir = self._base_path / "mypackage"
            pkg_dir.mkdir(exist_ok=True)
            (pkg_dir / "__init__.py").write_text("")
            (pkg_dir / "flows.py").write_text(
                "from prefect import flow\n\n@flow\ndef test_flow():\n    return 1\n"
            )

    def to_pull_step(self):
        return {"prefect.fake.module": {}}


@pytest.fixture
def temp_storage() -> Generator[MockStorage, Any, None]:
    with tempfile.TemporaryDirectory() as temp_dir:
        yield MockStorage(base_path=Path(temp_dir))


@pytest.fixture
def temp_module_storage() -> Generator[MockModuleStorage, Any, None]:
    with tempfile.TemporaryDirectory() as temp_dir:
        yield MockModuleStorage(base_path=Path(temp_dir))


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
        assert runner._limit_manager.acquire_for_flow_run(uuid.uuid4()) is True

    async def test_runner_respects_poll_setting(self):
        runner = Runner()
        assert runner.query_seconds == PREFECT_RUNNER_POLL_FREQUENCY.value()

        runner = Runner(query_seconds=50)
        assert runner.query_seconds == 50

        with temporary_settings({PREFECT_RUNNER_POLL_FREQUENCY: 100}):
            runner = Runner()
            assert runner.query_seconds == 100


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

        assert runner._deployment_registry.get_deployment_name(deployment_id_1) == (
            "test_runner"
        )
        assert runner._deployment_registry.get_deployment_name(deployment_id_2) == (
            "test_runner"
        )

    async def test_runner_name_with_dots_is_not_truncated(
        self, prefect_client: PrefectClient
    ):
        # regression test for https://github.com/PrefectHQ/prefect/issues/13528
        assert Runner(name="etl.hello").name == "etl.hello"
        assert Runner(name="my-runner-v1.2.3").name == "my-runner-v1.2.3"
        # an actual filename is still treated as one, like RunnerDeployment does
        assert Runner(name="flows.py").name == "flows"

        # `add_flow` defaults the deployment name to the runner name, so the
        # truncation leaked into the deployment name as well
        runner = Runner(name="etl.hello")
        deployment_id = await runner.add_flow(dummy_flow_1, interval=3600)
        deployment = await prefect_client.read_deployment(deployment_id)
        assert deployment.name == "etl.hello"

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

    async def test_runner_add_flow_clears_work_pool_on_existing_deployment(
        self, prefect_client: PrefectClient, work_pool
    ):
        """When a deployment previously assigned to a work pool is served
        locally via Runner.add_flow, the work pool config should be cleared
        so that runs execute locally."""

        @flow
        def test_flow_clear_wp():
            pass

        deployment_with_pool = RunnerDeployment(
            name="test-clear-work-pool",
            flow_name="test-flow-clear-wp",
            work_pool_name=work_pool.name,
        )
        deployment_id = await deployment_with_pool.apply()
        api_deployment = await prefect_client.read_deployment(deployment_id)
        assert api_deployment.work_pool_name == work_pool.name

        runner = Runner()
        await runner.add_flow(test_flow_clear_wp, name="test-clear-work-pool")

        api_deployment = await prefect_client.read_deployment(deployment_id)
        assert api_deployment.work_pool_name is None
        assert api_deployment.work_queue_name is None

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
    async def test_runner_executes_flow_runs(
        self,
        prefect_client: PrefectClient,
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

    async def test_runner_does_not_try_to_cancel_flow_run_if_no_process_id_is_found(
        self, prefect_client: PrefectClient
    ):
        """
        Regression test for https://github.com/PrefectHQ/prefect/issues/18106
        """
        runner_1 = Runner(pause_on_shutdown=False)
        runner_2 = Runner()
        deployment_id = await runner_1.add_deployment(
            await tired_flow.to_deployment(__file__)
        )

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        async with runner_2:
            runner_2._cancellation_manager.cancel = AsyncMock()
            execute_task = asyncio.create_task(runner_1.start(run_once=True))

            while True:
                await anyio.sleep(0.5)
                assert not execute_task.done(), "Execution ended earlier than expected"
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
        runner_2._cancellation_manager.cancel.assert_not_called()

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_runs_on_cancellation_hooks_for_remotely_stored_flows(
        self,
        prefect_client: PrefectClient,
        caplog: pytest.LogCaptureFixture,
        in_temporary_runner_directory: None,
        temp_storage: MockStorage,
    ):
        runner = Runner(query_seconds=1, pause_on_shutdown=False)

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

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        execute_task = asyncio.create_task(runner.start(run_once=True))
        # Need to wait for polling loop to pick up flow run and
        # start execution
        while True:
            await anyio.sleep(0.5)
            assert not execute_task.done(), "Execution ended earlier than expected"
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
        runner = Runner(query_seconds=2, pause_on_shutdown=False)

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

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        execute_task = asyncio.create_task(runner.start(run_once=True))
        # Need to wait for polling loop to pick up flow run and
        # start execution
        while True:
            await anyio.sleep(0.5)
            assert not execute_task.done(), "Execution ended earlier than expected"
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
        runner = Runner(pause_on_shutdown=False)
        temp_storage.code = dedent(
            """\
        import os

        from prefect import flow
        from prefect.logging.loggers import flow_run_logger

        def on_crashed(flow, flow_run, state):
            logger = flow_run_logger(flow_run, flow)
            logger.info("This flow crashed!")

        @flow(on_crashed=[on_crashed], log_prints=True)
        def crashing_flow():
            print("Oh boy, here I go crashing again...")
            os._exit(7)
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
        await runner.start(run_once=True)

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert flow_run.state
        assert flow_run.state.is_crashed()
        # check to make sure on_crashed hook was called
        assert "This flow crashed!" in caplog.text

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
    ):
        runner = Runner(limit=None, pause_on_shutdown=False)

        deployment_id = await runner.add_deployment(
            await dummy_flow.to_deployment(__file__)
        )

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )
        await runner.start(run_once=True)

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert flow_run.state
        assert flow_run.state.is_completed()

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
    async def test_runner_preserves_failed_engine_command_outcome(
        self,
        prefect_client: PrefectClient,
        temp_storage: MockStorage,
        caplog: pytest.LogCaptureFixture,
    ):
        observed_exit_codes: list[int | None] = []
        original_run_process = processutils.run_process

        async def run_process_and_record_exit_code(
            *args: Any, **kwargs: Any
        ) -> anyio.abc.Process:
            process = await original_run_process(*args, **kwargs)
            observed_exit_codes.append(process.returncode)
            return process

        temp_storage.code = dedent(
            """\
            from prefect import flow
            from prefect.logging.loggers import flow_run_logger

            def on_crashed(flow, flow_run, state):
                flow_run_logger(flow_run, flow).error("runner crash hook ran")

            @flow(on_crashed=[on_crashed])
            def failed_flow():
                raise ValueError("application failure")
            """
        )
        runner = Runner()
        deployment = await (
            await flow.from_source(
                source=temp_storage,
                entrypoint="flows.py:failed_flow",
            )
        ).to_deployment(__file__)
        deployment_id = await runner.add_deployment(deployment)
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        with patch(
            "prefect.runner._starter_engine.run_process",
            side_effect=run_process_and_record_exit_code,
        ):
            await runner.start(run_once=True)

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert flow_run.state is not None
        assert flow_run.state.is_failed()
        assert observed_exit_codes == [0]
        assert "runner crash hook ran" not in caplog.text
        assert "Process exited with status code: 1" not in caplog.text

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

        The runner has a race condition where it can try to submit a flow run
        that is already being submitted. This test ensures that the runner does
        not raise an exception in this case.
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
            # Mark the flow run as already being submitted to simulate the
            # race condition where a poll discovers a run already in progress.
            # The poller uses _submitting_flow_run_ids to deduplicate.
            runner._limit_manager.acquire_for_flow_run(flow_run.id)
            runner._scheduled_run_poller._submitting_flow_run_ids.add(flow_run.id)
            await runner._get_and_submit_flow_runs()

            # shut down cleanly
            runner.started = False
            runner.stopping = True
            runner._cancelling_flow_run_ids.add(flow_run.id)
            await runner._cancel_run(flow_run)

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_runner_process_manager_remove_unregisters_control_channel(self):
        flow_run_id = uuid.uuid4()

        async with Runner() as runner:
            runner._control_channel.unregister = MagicMock()
            await runner._process_manager.remove(flow_run_id)

        runner._control_channel.unregister.assert_called_once_with(flow_run_id)

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

        # Runner should continue running without crashing

        # Runner should continue running without crashing

        # Runner should have handled the ObjectNotFound gracefully


@pytest.mark.usefixtures("use_hosted_api_server")
async def test_runner_emits_cancelled_event(
    mock_events_client: AssertingEventsClient,
    reset_worker_events,
    prefect_client: PrefectClient,
    temp_storage: MockStorage,
    in_temporary_runner_directory: None,
):
    runner = Runner(query_seconds=1, pause_on_shutdown=False)
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

    execute_task = asyncio.create_task(runner.start(run_once=True))
    while True:
        await anyio.sleep(0.5)
        assert not execute_task.done(), "Execution ended earlier than expected"
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


async def test_runner_can_execute_instance_method_flow(
    prefect_client: PrefectClient,
):
    """Test that instance method flows can be executed via multiprocessing."""
    runner = Runner(query_seconds=1, pause_on_shutdown=False)

    # Create an instance and add its flow method
    flow_instance = ClassWithInstanceMethod(10)
    deployment_id = await runner.add_flow(
        flow_instance.instance_method_flow,
        name="instance-method-test",
    )

    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment_id,
        parameters={"x": 5},
    )

    await runner.start(run_once=True)

    flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
    assert flow_run.state
    assert flow_run.state.is_completed()


async def test_runner_runs_on_cancellation_hooks_for_instance_method_flows(
    prefect_client: PrefectClient,
    caplog: pytest.LogCaptureFixture,
):
    """Test that cancellation hooks work correctly for instance method flows."""
    runner = Runner(query_seconds=1, pause_on_shutdown=False)

    # Create an instance and add its flow method with cancellation hook
    flow_instance = ClassWithCancellableFlow()
    deployment_id = await runner.add_flow(
        flow_instance.cancellable_flow,
        name="cancellable-instance-method",
    )

    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment_id
    )

    execute_task = asyncio.create_task(runner.start(run_once=True))

    # Wait for flow to start running
    while True:
        await anyio.sleep(0.5)
        assert not execute_task.done(), "Execution ended earlier than expected"
        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert flow_run.state
        if flow_run.state.is_running():
            break

    # Cancel the flow run
    await prefect_client.set_flow_run_state(
        flow_run_id=flow_run.id,
        state=flow_run.state.model_copy(
            update={"name": "Cancelling", "type": StateType.CANCELLING}
        ),
    )

    await execute_task

    flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
    assert flow_run.state.is_cancelled()
    assert "Instance method flow was cancelled!" in caplog.text


async def test_runner_runs_on_crashed_hooks_for_instance_method_flows(
    prefect_client: PrefectClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Test that crashed hooks work correctly for instance method flows."""
    runner = Runner(pause_on_shutdown=False)

    # Create an instance and add its flow method with crashed hook
    flow_instance = ClassWithCrashingFlow()
    deployment_id = await runner.add_flow(
        flow_instance.crashing_flow,
        name="crashing-instance-method",
    )

    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment_id
    )
    hook_marker = tmp_path / "instance-crash-hook"
    monkeypatch.setenv("PREFECT_TEST_INSTANCE_CRASH_HOOK_MARKER", str(hook_marker))

    await runner.start(run_once=True)

    flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
    assert flow_run.state
    assert flow_run.state.is_crashed()
    assert hook_marker.exists()


async def test_run_hooks_with_partial_hooks(
    caplog: pytest.LogCaptureFixture,
):
    """Test that _run_hooks correctly handles functools.partial hooks.

    This test verifies that partial hooks don't cause AttributeError when
    accessing hook names, which was a bug where hook.__name__ was accessed
    directly instead of using get_hook_name().
    """
    from functools import partial

    from prefect.runner._hook_runner import _run_hooks
    from prefect.states import Cancelled

    data = {}

    def my_hook(flow, flow_run, state, **kwargs):
        data.update(name=my_hook.__name__, state=state, kwargs=kwargs)

    partial_hook = partial(my_hook, extra_arg="test_value")

    mock_flow = MagicMock()
    mock_flow.name = "test-flow"

    mock_flow_run = MagicMock()
    mock_flow_run.id = uuid.uuid4()
    mock_flow_run.name = "test-flow-run"

    state = Cancelled(message="Test cancellation")

    await _run_hooks([partial_hook], mock_flow_run, mock_flow, state)

    assert data["name"] == "my_hook"
    assert data["state"] == state
    assert data["kwargs"] == {"extra_arg": "test_value"}
    assert "Running hook 'my_hook'" in caplog.text
    assert "Hook 'my_hook' finished running successfully" in caplog.text


class TestRunnerDeployment:
    @pytest.fixture
    async def saved_secret_block(self) -> tuple[Secret[Any], uuid.UUID]:
        block = Secret(value="issue-13122-secret")
        block_document_id = await block.save(f"deployment-parameter-{uuid.uuid4()}")
        return block, block_document_id

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
        # `DeploymentScheduleCreate` injects an explicit DTSTART so the
        # scheduler doesn't walk from the legacy 2020 anchor (#21362).
        assert deployment.schedules[0].schedule.rrule.endswith("FREQ=MINUTELY")

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
        assert deployment.schedules[0].schedule.rrule.endswith("FREQ=DAILY")
        assert deployment.schedules[1].schedule.rrule.endswith("FREQ=WEEKLY")
        assert deployment.schedules[2].schedule.rrule.endswith("FREQ=MONTHLY")

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

    async def test_from_flow_accepts_concurrency_limit_config_with_grace_period(self):
        """Test that grace_period_seconds is properly extracted from ConcurrencyLimitConfig."""
        concurrency_limit_config = ConcurrencyLimitConfig(
            limit=42, collision_strategy="CANCEL_NEW", grace_period_seconds=120
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
        assert (
            deployment.concurrency_options.grace_period_seconds
            == concurrency_limit_config.grace_period_seconds
        )

    async def test_from_flow_concurrency_limit_config_without_grace_period(self):
        """Test that grace_period_seconds defaults when not provided in ConcurrencyLimitConfig."""
        concurrency_limit_config = ConcurrencyLimitConfig(
            limit=42, collision_strategy="ENQUEUE"
        )
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1,
            __file__,
            concurrency_limit=concurrency_limit_config,
        )
        assert deployment.concurrency_limit == concurrency_limit_config.limit
        assert deployment.concurrency_options is not None
        # When grace_period_seconds is not set in ConcurrencyLimitConfig,
        # it should not be included in the concurrency_options dict passed to deployment
        # (the ConcurrencyOptions model defaults to None, server setting is used at runtime)
        assert deployment.concurrency_options.grace_period_seconds is None

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

    def test_from_flow_source_outside_cwd(self, tmp_path):
        with mock.patch(
            "prefect.deployments.runner.Path.cwd",
            return_value=tmp_path,
        ):
            deployment = RunnerDeployment.from_flow(dummy_flow_1, __file__)

        assert deployment.entrypoint.endswith(":dummy_flow_1")
        # The flow file is outside tmp_path, so os.path.relpath should be used
        expected_relpath = os.path.relpath(Path(__file__).absolute(), tmp_path)
        assert deployment.entrypoint == f"{expected_relpath}:dummy_flow_1"

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
        assert deployment.schedules[0].schedule.rrule.endswith("FREQ=MINUTELY")

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
        assert deployment.schedules[0].schedule.rrule.endswith("FREQ=DAILY")
        assert deployment.schedules[1].schedule.rrule.endswith("FREQ=WEEKLY")
        assert deployment.schedules[2].schedule.rrule.endswith("FREQ=MONTHLY")

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

    @pytest.mark.parametrize("clear_schedules", [False, True])
    @pytest.mark.parametrize("slug", [None, "daily"])
    @pytest.mark.parametrize(
        "apply_kwargs, expected_cron",
        [
            pytest.param({}, "0 4 * * *", id="omitted"),
            pytest.param({"schedules": None}, "0 4 * * *", id="none"),
            pytest.param({"schedules": []}, None, id="empty"),
            pytest.param(
                {"schedules": [{"schedule": CronSchedule(cron="0 5 * * *")}]},
                "0 5 * * *",
                id="populated",
            ),
        ],
    )
    async def test_aapply_existing_deployment_schedules(
        self,
        prefect_client: PrefectClient,
        apply_kwargs: dict[str, Any],
        expected_cron: str | None,
        clear_schedules: bool,
        slug: str | None,
    ):
        original = RunnerDeployment.from_flow(
            dummy_flow_1,
            name="schedule-update",
            schedules=[
                DeploymentScheduleCreate(
                    schedule=CronSchedule(cron="0 4 * * *"), slug=slug
                )
            ],
            version_type=VersionType.SIMPLE,
        )
        deployment_id = await original.aapply()
        before = await prefect_client.read_deployment(deployment_id)
        assert len(before.schedules) == 1
        assert before.schedules[0].active is True

        deployment = RunnerDeployment(
            name=original.name,
            flow_name=original.flow_name,
            version_type=VersionType.SIMPLE,
        )
        if apply_kwargs.get("schedules"):
            apply_kwargs = {
                "schedules": [{**apply_kwargs["schedules"][0], "slug": slug}]
            }
        with temporary_settings(
            {"deployments.clear_schedules_on_empty": clear_schedules}
        ):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", FutureWarning)
                updated_id = await deployment.aapply(**apply_kwargs)

        deprecations = [w for w in caught if issubclass(w.category, FutureWarning)]
        if apply_kwargs.get("schedules") == [] and not clear_schedules:
            assert len(deprecations) == 1
            message = str(deprecations[0].message)
            assert "PREFECT_DEPLOYMENTS_CLEAR_SCHEDULES_ON_EMPTY=true" in message
            assert "six months or three minor releases, whichever is longer" in message
            assert "schedules=None" in message
            expected_cron = "0 4 * * *"
        else:
            assert deprecations == []

        assert updated_id == deployment_id
        updated = await prefect_client.read_deployment(deployment_id)
        assert updated.paused is False
        if expected_cron is None:
            assert updated.schedules == []
        else:
            assert len(updated.schedules) == 1
            assert updated.schedules[0].schedule == CronSchedule(cron=expected_cron)
            assert updated.schedules[0].active is True
            if expected_cron == "0 4 * * *":
                assert updated.schedules[0].id == before.schedules[0].id

    @pytest.mark.parametrize("sync", [False, True])
    @pytest.mark.parametrize("clear_schedules", [False, True])
    @pytest.mark.parametrize("slug", [None, "daily"])
    @pytest.mark.parametrize("preset", ["empty", "populated", "previously-cleared"])
    async def test_empty_schedule_override_with_preset_schedules(
        self,
        prefect_client: PrefectClient,
        sync: bool,
        clear_schedules: bool,
        slug: str | None,
        preset: str,
    ):
        original = RunnerDeployment.from_flow(
            dummy_flow_1,
            name="preset-schedules",
            schedules=[
                DeploymentScheduleCreate(
                    schedule=CronSchedule(cron="0 4 * * *"), slug=slug
                )
            ],
            version_type=VersionType.SIMPLE,
        )
        deployment_id = await original.aapply()
        if preset == "previously-cleared":
            deployment = original
            with temporary_settings({"deployments.clear_schedules_on_empty": True}):
                if sync:
                    await run_sync_in_worker_thread(
                        deployment.apply, schedules=[], _sync=True
                    )
                else:
                    await deployment.aapply(schedules=[])
            # Restore a server-side schedule, then reuse the cleared object.
            await prefect_client.create_deployment_schedules(
                deployment_id,
                [
                    DeploymentScheduleCreate(
                        schedule=CronSchedule(cron="0 4 * * *"), slug=slug
                    )
                ],
            )
        else:
            deployment = RunnerDeployment.from_flow(
                dummy_flow_1,
                name=original.name,
                schedules=(
                    [
                        DeploymentScheduleCreate(
                            schedule=CronSchedule(cron="0 5 * * *"), slug=slug
                        )
                    ]
                    if preset == "populated"
                    else []
                ),
                version_type=VersionType.SIMPLE,
            )

        before = await prefect_client.read_deployment(deployment_id)
        assert len(before.schedules) == 1
        preset_schedules = list(deployment.schedules)
        deployment.description = "Updated without replacing preserved schedules"
        with (
            temporary_settings(
                {"deployments.clear_schedules_on_empty": clear_schedules}
            ),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always", FutureWarning)
            if sync:
                updated_id = await run_sync_in_worker_thread(
                    deployment.apply, schedules=[], _sync=True
                )
            else:
                updated_id = await deployment.aapply(schedules=[])

        deprecations = [w for w in caught if issubclass(w.category, FutureWarning)]
        assert len(deprecations) == (0 if clear_schedules else 1)
        assert updated_id == deployment_id
        after = await prefect_client.read_deployment(deployment_id)
        assert after.description == deployment.description
        assert after.paused == before.paused
        if clear_schedules:
            assert after.schedules == []
        else:
            assert after.schedules == before.schedules
            assert deployment.schedules == preset_schedules

    @pytest.mark.parametrize("sync", [False, True])
    @pytest.mark.parametrize(
        "slugs", [[], [None, None], [None, "daily"], ["daily", "nightly"]]
    )
    async def test_opt_in_clears_all_schedules(
        self, prefect_client: PrefectClient, sync: bool, slugs: list[str | None]
    ):
        original = RunnerDeployment.from_flow(
            dummy_flow_1,
            name="clear-all-schedules",
            schedules=[
                DeploymentScheduleCreate(
                    schedule=CronSchedule(cron=f"0 {hour} * * *"), slug=slug
                )
                for hour, slug in enumerate(slugs)
            ],
            version_type=VersionType.SIMPLE,
        )
        deployment_id = await original.aapply()
        deployment = RunnerDeployment(
            name=original.name,
            flow_name=original.flow_name,
            version_type=VersionType.SIMPLE,
        )
        with temporary_settings({"deployments.clear_schedules_on_empty": True}):
            # Clearing an already empty deployment must also succeed.
            for _ in range(2):
                if sync:
                    updated_id = await run_sync_in_worker_thread(
                        deployment.apply, schedules=[], _sync=True
                    )
                else:
                    updated_id = await deployment.aapply(schedules=[])
                assert updated_id == deployment_id
                assert (
                    await prefect_client.read_deployment(deployment_id)
                ).schedules == []

    @pytest.mark.parametrize("sync", [False, True])
    @pytest.mark.parametrize("clear_schedules", [False, True])
    async def test_new_deployment_with_empty_schedules_does_not_warn(
        self, prefect_client: PrefectClient, sync: bool, clear_schedules: bool
    ):
        deployment = RunnerDeployment(
            name="new-empty-schedules",
            flow_name="empty-schedules",
            version_type=VersionType.SIMPLE,
        )
        with temporary_settings(
            {"deployments.clear_schedules_on_empty": clear_schedules}
        ):
            # Warnings are errors under the test suite's default filter.
            if sync:
                deployment_id = await run_sync_in_worker_thread(
                    deployment.apply, schedules=[], _sync=True
                )
            else:
                deployment_id = await deployment.aapply(schedules=[])
        assert (await prefect_client.read_deployment(deployment_id)).schedules == []

    @pytest.mark.parametrize("sync", [False, True])
    async def test_failed_update_does_not_clear_slugged_schedules(
        self, prefect_client: PrefectClient, sync: bool
    ):
        @flow
        def parameterized(value: int = 1):
            pass

        deployment = RunnerDeployment.from_flow(
            parameterized,
            name="invalid-update",
            schedules=[
                DeploymentScheduleCreate(
                    schedule=CronSchedule(cron="0 4 * * *"), slug="daily"
                )
            ],
            version_type=VersionType.SIMPLE,
        )
        deployment_id = await deployment.aapply()
        before = await prefect_client.read_deployment(deployment_id)
        deployment.parameters = {"value": "invalid integer"}
        with temporary_settings({"deployments.clear_schedules_on_empty": True}):
            with pytest.raises(PrefectHTTPStatusError, match="409"):
                if sync:
                    await run_sync_in_worker_thread(
                        deployment.apply, schedules=[], _sync=True
                    )
                else:
                    await deployment.aapply(schedules=[])
        after = await prefect_client.read_deployment(deployment_id)
        assert after.schedules == before.schedules

    async def test_saved_block_parameters_are_converted_to_references(
        self, saved_secret_block: tuple[Secret[Any], uuid.UUID]
    ):
        block, block_document_id = saved_secret_block

        class BlockParameterModel(BaseModel):
            block: Secret

        deployment = RunnerDeployment(
            name="saved-block-parameter",
            flow_name="flow-with-block",
            parameters={
                "nested": {
                    "blocks": [block],
                    "model": BlockParameterModel(block=block),
                }
            },
        )

        assert deployment.parameters["nested"]["blocks"][0] is block
        assert deployment.model_dump(mode="json")["parameters"] == {
            "nested": {
                "blocks": [
                    {
                        "$ref": {
                            "block_document_id": str(block_document_id),
                        }
                    }
                ],
                "model": {
                    "block": {
                        "$ref": {
                            "block_document_id": str(block_document_id),
                        }
                    }
                },
            }
        }

    def test_unsaved_block_parameters_are_rejected(self):
        with pytest.raises(
            BlockNotSavedError,
            match=re.escape(
                "Block must be saved with `.save()` before it can be used as a "
                "deployment parameter."
            ),
        ):
            RunnerDeployment(
                name="unsaved-block-parameter",
                flow_name="flow-with-block",
                parameters={"block": Secret(value="secret")},
            )

    def test_unsaved_block_schedule_parameters_are_rejected(self):
        with pytest.raises(
            BlockNotSavedError,
            match=re.escape(
                "Block must be saved with `.save()` before it can be used as a "
                "deployment parameter."
            ),
        ):
            RunnerDeployment(
                name="unsaved-block-schedule-parameter",
                flow_name="flow-with-block",
                schedules=[
                    DeploymentScheduleCreate(
                        schedule=IntervalSchedule(interval=datetime.timedelta(days=1)),
                        parameters={"block": Secret(value="secret")},
                    )
                ],
            )

    async def test_applied_deployment_preserves_temporal_parameter_encoding(
        self, prefect_client: PrefectClient
    ):
        scheduled_at = datetime.datetime(
            2024, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc
        )
        delay = datetime.timedelta(seconds=90)

        @flow
        def flow_with_temporal_parameters(
            scheduled_at: str | datetime.datetime,
            delay: datetime.timedelta,
        ) -> None:
            pass

        deployment = await flow_with_temporal_parameters.ato_deployment(
            name="temporal-parameters",
            parameters={"scheduled_at": scheduled_at, "delay": delay},
            enforce_parameter_schema=False,
        )

        deployment_id = await deployment.apply()
        stored_deployment = await prefect_client.read_deployment(deployment_id)

        assert stored_deployment.parameters == {
            "scheduled_at": scheduled_at.timestamp(),
            "delay": delay.total_seconds(),
        }
        validated_parameters = flow_with_temporal_parameters.validate_parameters(
            stored_deployment.parameters
        )
        assert validated_parameters == {
            "scheduled_at": scheduled_at,
            "delay": delay,
        }

    async def test_applied_deployment_stores_and_resolves_saved_block_parameter(
        self,
        prefect_client: PrefectClient,
        saved_secret_block: tuple[Secret[Any], uuid.UUID],
    ):
        block, block_document_id = saved_secret_block

        @flow
        def flow_with_block(credentials: Secret[Any]) -> str:
            return str(credentials.get())

        deployment = await flow_with_block.ato_deployment(
            name="saved-block-parameter",
            parameters={"credentials": block},
        )

        deployment_id = await deployment.apply()
        stored_deployment = await prefect_client.read_deployment(deployment_id)

        assert stored_deployment.parameters == {
            "credentials": {
                "$ref": {
                    "block_document_id": str(block_document_id),
                }
            }
        }
        validated_parameters = flow_with_block.validate_parameters(
            stored_deployment.parameters
        )
        assert validated_parameters["credentials"].get() == "issue-13122-secret"

        updated_block = Secret(value="updated-secret")
        updated_block_document_id = await updated_block.save(
            f"updated-deployment-parameter-{uuid.uuid4()}"
        )
        deployment.parameters = {"credentials": updated_block}

        updated_deployment_id = await deployment.apply()
        updated_deployment = await prefect_client.read_deployment(updated_deployment_id)

        assert updated_deployment_id == deployment_id
        assert updated_deployment.parameters == {
            "credentials": {
                "$ref": {
                    "block_document_id": str(updated_block_document_id),
                }
            }
        }
        updated_parameters = flow_with_block.validate_parameters(
            updated_deployment.parameters
        )
        assert updated_parameters["credentials"].get() == "updated-secret"

    async def test_applied_deployment_stores_saved_block_schedule_parameter(
        self,
        prefect_client: PrefectClient,
        saved_secret_block: tuple[Secret[Any], uuid.UUID],
    ):
        block, block_document_id = saved_secret_block

        @flow
        def flow_with_block(credentials: Secret[Any]) -> str:
            return str(credentials.get())

        deployment = await flow_with_block.ato_deployment(
            name="saved-block-schedule-parameter",
            schedules=[
                DeploymentScheduleCreate(
                    schedule=IntervalSchedule(interval=datetime.timedelta(days=1)),
                    parameters={"credentials": block},
                    slug="saved-block",
                )
            ],
        )

        deployment_id = await deployment.apply()
        stored_deployment = await prefect_client.read_deployment(deployment_id)

        assert stored_deployment.schedules[0].parameters == {
            "credentials": {
                "$ref": {
                    "block_document_id": str(block_document_id),
                }
            }
        }
        validated_parameters = flow_with_block.validate_parameters(
            stored_deployment.schedules[0].parameters
        )
        assert validated_parameters["credentials"].get() == "issue-13122-secret"

        updated_block = Secret(value="updated-schedule-secret")
        updated_block_document_id = await updated_block.save(
            f"updated-schedule-parameter-{uuid.uuid4()}"
        )
        assert deployment.schedules is not None
        deployment.schedules[0].parameters = {"credentials": updated_block}

        updated_deployment_id = await deployment.apply()
        updated_deployment = await prefect_client.read_deployment(updated_deployment_id)

        assert updated_deployment_id == deployment_id
        assert updated_deployment.schedules[0].parameters == {
            "credentials": {
                "$ref": {
                    "block_document_id": str(updated_block_document_id),
                }
            }
        }
        updated_parameters = flow_with_block.validate_parameters(
            updated_deployment.schedules[0].parameters
        )
        assert updated_parameters["credentials"].get() == "updated-schedule-secret"

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

        # re-applying without job variables clears the previously stored overrides
        assert deployment2.job_variables == {}
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

    def test_deployment_name_with_dots_from_storage(self, temp_storage: MockStorage):
        # regression test for deployment name truncation in from_storage
        # names with dots like "v2.0.1" should not be truncated to "v2"
        deployment = RunnerDeployment.from_storage(
            storage=temp_storage,
            entrypoint="flows.py:test_flow",
            name="pricing-subflow-v2.0.1",
        )
        assert deployment.name == "pricing-subflow-v2.0.1"

        # test with multiple dots
        deployment2 = RunnerDeployment.from_storage(
            storage=temp_storage,
            entrypoint="flows.py:test_flow",
            name="my-flow-v1.2.3.4",
        )
        assert deployment2.name == "my-flow-v1.2.3.4"

    async def test_deployment_name_with_dots_from_storage_async(
        self, temp_storage: MockStorage
    ):
        # regression test for deployment name truncation in afrom_storage
        deployment = await RunnerDeployment.afrom_storage(
            storage=temp_storage,
            entrypoint="flows.py:test_flow",
            name="pricing-subflow-v2.0.1",
        )
        assert deployment.name == "pricing-subflow-v2.0.1"

    def test_from_storage_with_module_path_entrypoint(
        self, temp_module_storage: MockModuleStorage
    ):
        deployment = RunnerDeployment.from_storage(
            storage=temp_module_storage,
            entrypoint="mypackage.flows.test_flow",
            name="test-deployment",
        )
        assert isinstance(deployment, RunnerDeployment)
        assert deployment.flow_name == "test-flow"
        assert deployment.entrypoint == "mypackage.flows.test_flow"
        assert deployment._entrypoint_type == EntrypointType.MODULE_PATH

    async def test_from_storage_with_module_path_entrypoint_async(
        self, temp_module_storage: MockModuleStorage
    ):
        deployment = await RunnerDeployment.afrom_storage(
            storage=temp_module_storage,
            entrypoint="mypackage.flows.test_flow",
            name="test-deployment",
        )
        assert isinstance(deployment, RunnerDeployment)
        assert deployment.flow_name == "test-flow"
        assert deployment.entrypoint == "mypackage.flows.test_flow"
        assert deployment._entrypoint_type == EntrypointType.MODULE_PATH

    def test_from_storage_with_module_path_does_not_pollute_sys_path(
        self, temp_module_storage: MockModuleStorage
    ):
        original_path = sys.path.copy()

        RunnerDeployment.from_storage(
            storage=temp_module_storage,
            entrypoint="mypackage.flows.test_flow",
            name="test-deployment",
        )

        assert sys.path == original_path

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

    async def test_run_count_reports_tracked_flow_runs(self):
        runner = Runner()
        get_run_count = run_count(runner)
        assert get_run_count() == 0

        flow_run_ids = [uuid.uuid4(), uuid.uuid4()]
        for flow_run_id in flow_run_ids:
            await runner._process_manager.add(flow_run_id, ProcessHandle(MagicMock()))
        assert get_run_count() == 2

        for flow_run_id in flow_run_ids:
            await runner._process_manager.remove(flow_run_id)
        assert get_run_count() == 0

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


def maintenance_response(retry_after: str) -> httpx.Response:
    return httpx.Response(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        headers={"Prefect-Maintenance": "true", "Retry-After": retry_after},
    )


class TestHealthCheckDuringServerMaintenance:
    # The default window: 2 missed polls x 10s poll frequency.
    DELAY_THRESHOLD = 20

    @pytest.fixture(autouse=True)
    def disable_jitter(self) -> Generator[None, None, None]:
        with temporary_settings({PREFECT_CLIENT_RETRY_JITTER_FACTOR: 0}):
            yield

    @pytest.fixture
    def mock_clock(
        self, mock_anyio_sleep: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> AsyncMock:
        # The health check and the poller import `now` directly; have them
        # follow the clock that `mock_anyio_sleep` advances.
        monkeypatch.setattr("prefect.runner.server.now_fn", prefect.types._datetime.now)
        monkeypatch.setattr(
            "prefect.runner._scheduled_run_poller.now", prefect.types._datetime.now
        )
        return mock_anyio_sleep

    def mock_scheduled_flow_runs(
        self, respx_mock: respx.MockRouter, side_effect: Any
    ) -> None:
        respx_mock.post(path__regex=r"/deployments/get_scheduled_flow_runs$").mock(
            side_effect=side_effect
        )
        respx_mock.route().pass_through()

    async def test_runner_waiting_out_maintenance_reports_healthy(
        self, respx_mock: respx.MockRouter, mock_clock: AsyncMock
    ):
        runner = Runner()
        health_check = perform_health_check(
            runner, delay_threshold=self.DELAY_THRESHOLD
        )
        health_at_each_attempt: list[int] = []

        def in_maintenance_for_three_attempts(request: httpx.Request) -> httpx.Response:
            health_at_each_attempt.append(health_check().status_code)
            if len(health_at_each_attempt) <= 3:
                return maintenance_response("200")
            return httpx.Response(status.HTTP_200_OK, json=[])

        self.mock_scheduled_flow_runs(respx_mock, in_maintenance_for_three_attempts)
        async with runner:
            runner.last_polled = prefect.types._datetime.now("UTC")
            await runner._scheduled_run_poller._get_and_submit_flow_runs()

        # The last three attempts come 200s, 400s and 600s after the previous
        # poll, far past the 20s window, while the poll waits out maintenance.
        assert health_at_each_attempt == [status.HTTP_200_OK] * 4

    async def test_runner_gets_the_polling_window_after_maintenance_ends(
        self, respx_mock: respx.MockRouter, mock_clock: AsyncMock
    ):
        runner = Runner()
        health_check = perform_health_check(
            runner, delay_threshold=self.DELAY_THRESHOLD
        )
        attempts: list[tuple[datetime.datetime, int]] = []

        def unavailable_after_maintenance(request: httpx.Request) -> httpx.Response:
            attempts.append(
                (prefect.types._datetime.now("UTC"), health_check().status_code)
            )
            if len(attempts) <= 3:
                return maintenance_response("200")
            # Maintenance is over, but the API is not answering yet.
            return httpx.Response(status.HTTP_503_SERVICE_UNAVAILABLE)

        self.mock_scheduled_flow_runs(respx_mock, unavailable_after_maintenance)
        async with runner:
            runner.last_polled = prefect.types._datetime.now("UTC")
            with temporary_settings({PREFECT_CLIENT_MAX_RETRIES: 0}):
                with pytest.raises(PrefectHTTPStatusError):
                    await runner._scheduled_run_poller._get_and_submit_flow_runs()

            assert all(code == status.HTTP_200_OK for _, code in attempts)

            # The first attempt after the last maintenance back-off.
            maintenance_ended_at = attempts[3][0]
            await anyio.sleep(
                (
                    maintenance_ended_at
                    + datetime.timedelta(seconds=self.DELAY_THRESHOLD - 1)
                    - prefect.types._datetime.now("UTC")
                ).total_seconds()
            )
            assert health_check().status_code == status.HTTP_200_OK

            await anyio.sleep(2)
            assert health_check().status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    async def test_ordinary_retries_do_not_extend_the_polling_window(
        self, respx_mock: respx.MockRouter, mock_clock: AsyncMock
    ):
        runner = Runner()
        health_check = perform_health_check(
            runner, delay_threshold=self.DELAY_THRESHOLD
        )
        health_at_each_attempt: list[int] = []

        def unavailable_without_maintenance(request: httpx.Request) -> httpx.Response:
            health_at_each_attempt.append(health_check().status_code)
            if len(health_at_each_attempt) <= 3:
                return httpx.Response(
                    status.HTTP_503_SERVICE_UNAVAILABLE, headers={"Retry-After": "200"}
                )
            return httpx.Response(status.HTTP_200_OK, json=[])

        self.mock_scheduled_flow_runs(respx_mock, unavailable_without_maintenance)
        async with runner:
            runner.last_polled = prefect.types._datetime.now("UTC")
            await runner._scheduled_run_poller._get_and_submit_flow_runs()

        # Same timings as maintenance, but these retries do not extend the window.
        assert health_at_each_attempt == [
            status.HTTP_200_OK,
            status.HTTP_503_SERVICE_UNAVAILABLE,
            status.HTTP_503_SERVICE_UNAVAILABLE,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ]

    async def test_healthcheck_uses_the_polling_window_before_the_first_poll(
        self, mock_clock: AsyncMock
    ):
        runner = Runner()
        health_check = perform_health_check(
            runner, delay_threshold=self.DELAY_THRESHOLD
        )

        await anyio.sleep(self.DELAY_THRESHOLD - 1)
        assert health_check().status_code == status.HTTP_200_OK

        record_maintenance_backoff(600)
        await anyio.sleep(600 + self.DELAY_THRESHOLD - 1)
        assert health_check().status_code == status.HTTP_200_OK

        await anyio.sleep(2)
        assert health_check().status_code == status.HTTP_503_SERVICE_UNAVAILABLE

        runner.last_polled = prefect.types._datetime.now("UTC")
        assert health_check().status_code == status.HTTP_200_OK


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
            tag="test-registry/test-image:test-tag",
            context=Path.cwd(),
            pull=True,
            stream_progress_to=ANY,
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
                tag="test-registry/test-image:test-tag",
                context=Path.cwd(),
                pull=True,
                stream_progress_to=ANY,
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
            tag="test-registry/test-image:test-tag",
            context=Path.cwd(),
            pull=True,
            stream_progress_to=ANY,
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
            stream_progress_to=ANY,
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
            tag="test-registry/test-image:test-tag",
            context=Path.cwd(),
            pull=True,
            stream_progress_to=ANY,
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
            stream_progress_to=None,
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


class TestCancellationObserverFailureHandling:
    """Tests for the _handle_cancellation_observer_failure method."""

    @pytest.fixture
    def runner(self):
        return Runner(name="test-runner")

    async def test_sets_stopping_flag_when_crash_enabled(self, runner):
        """Should set stopping=True when crash_on_cancellation_failure is enabled."""
        from prefect.settings import PREFECT_RUNNER_CRASH_ON_CANCELLATION_FAILURE

        assert runner.stopping is False

        with temporary_settings({PREFECT_RUNNER_CRASH_ON_CANCELLATION_FAILURE: True}):
            await runner._handle_cancellation_observer_failure()

        assert runner.stopping is True

    async def test_does_not_set_stopping_flag_when_crash_disabled(self, runner):
        """Should not set stopping flag when crash_on_cancellation_failure is disabled."""
        assert runner.stopping is False

        await runner._handle_cancellation_observer_failure()

        assert runner.stopping is False


class TestAsyncDispatch:
    """Tests for async_dispatch behavior of RunnerDeployment.apply and deploy."""

    async def test_apply_in_async_context(self, prefect_client: PrefectClient):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1, __file__, interval=3600, version_type=VersionType.SIMPLE
        )

        deployment_id = await deployment.apply()

        result = await prefect_client.read_deployment(deployment_id)
        assert result.name == "test_runner"

    def test_apply_in_sync_context(self, sync_prefect_client: SyncPrefectClient):
        deployment = RunnerDeployment.from_flow(
            dummy_flow_1, __file__, interval=3600, version_type=VersionType.SIMPLE
        )

        deployment_id = deployment.apply()

        result = sync_prefect_client.read_deployment(deployment_id)
        assert result.name == "test_runner"

    @pytest.mark.parametrize("clear_schedules", [False, True])
    @pytest.mark.parametrize("slug", [None, "daily"])
    @pytest.mark.parametrize(
        "apply_kwargs, expected_cron",
        [
            pytest.param({}, "0 4 * * *", id="omitted"),
            pytest.param({"schedules": None}, "0 4 * * *", id="none"),
            pytest.param({"schedules": []}, None, id="empty"),
            pytest.param(
                {"schedules": [{"schedule": CronSchedule(cron="0 5 * * *")}]},
                "0 5 * * *",
                id="populated",
            ),
        ],
    )
    def test_apply_existing_deployment_schedules(
        self,
        sync_prefect_client: SyncPrefectClient,
        apply_kwargs: dict[str, Any],
        expected_cron: str | None,
        clear_schedules: bool,
        slug: str | None,
    ):
        original = RunnerDeployment.from_flow(
            dummy_flow_1,
            name="schedule-update",
            schedules=[
                DeploymentScheduleCreate(
                    schedule=CronSchedule(cron="0 4 * * *"), slug=slug
                )
            ],
            version_type=VersionType.SIMPLE,
        )
        deployment_id = original.apply()
        before = sync_prefect_client.read_deployment(deployment_id)
        assert len(before.schedules) == 1
        assert before.schedules[0].active is True

        deployment = RunnerDeployment(
            name=original.name,
            flow_name=original.flow_name,
            version_type=VersionType.SIMPLE,
        )
        if apply_kwargs.get("schedules"):
            apply_kwargs = {
                "schedules": [{**apply_kwargs["schedules"][0], "slug": slug}]
            }
        with temporary_settings(
            {"deployments.clear_schedules_on_empty": clear_schedules}
        ):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", FutureWarning)
                updated_id = deployment.apply(**apply_kwargs)

        deprecations = [w for w in caught if issubclass(w.category, FutureWarning)]
        if apply_kwargs.get("schedules") == [] and not clear_schedules:
            assert len(deprecations) == 1
            message = str(deprecations[0].message)
            assert "PREFECT_DEPLOYMENTS_CLEAR_SCHEDULES_ON_EMPTY=true" in message
            assert "six months or three minor releases, whichever is longer" in message
            assert "schedules=None" in message
            expected_cron = "0 4 * * *"
        else:
            assert deprecations == []

        assert updated_id == deployment_id
        updated = sync_prefect_client.read_deployment(deployment_id)
        assert updated.paused is False
        if expected_cron is None:
            assert updated.schedules == []
        else:
            assert len(updated.schedules) == 1
            assert updated.schedules[0].schedule == CronSchedule(cron=expected_cron)
            assert updated.schedules[0].active is True
            if expected_cron == "0 4 * * *":
                assert updated.schedules[0].id == before.schedules[0].id

    def test_apply_saved_block_parameter_in_sync_context(
        self, sync_prefect_client: SyncPrefectClient
    ):
        block = Secret(value="sync-secret")
        block_document_id = block.save(
            f"sync-deployment-parameter-{uuid.uuid4()}",
            client=sync_prefect_client,
        )

        @flow
        def flow_with_block(credentials: Secret[Any]) -> str:
            return str(credentials.get())

        deployment = flow_with_block.to_deployment(
            name="sync-saved-block-parameter",
            parameters={"credentials": block},
        )

        deployment_id = deployment.apply()
        stored_deployment = sync_prefect_client.read_deployment(deployment_id)

        assert stored_deployment.parameters == {
            "credentials": {
                "$ref": {
                    "block_document_id": str(block_document_id),
                }
            }
        }

    async def test_deploy_in_async_context(
        self,
        prefect_client: PrefectClient,
        work_pool_with_image_variable,
        monkeypatch,
    ):
        monkeypatch.setattr("prefect.docker.docker_image.build_image", MagicMock())
        mock_docker = MagicMock()
        mock_docker.return_value.__enter__.return_value = mock_docker
        mock_docker.api.push.return_value = []
        monkeypatch.setattr("prefect.docker.docker_image.docker_client", mock_docker)
        monkeypatch.setattr(
            "prefect.docker.docker_image.generate_default_dockerfile", MagicMock()
        )

        deployment = RunnerDeployment.from_flow(
            dummy_flow_1, __file__, interval=3600, version_type=VersionType.SIMPLE
        )

        deployment_ids = await deploy(
            deployment,
            work_pool_name=work_pool_with_image_variable.name,
            image="test-image",
        )

        result = await prefect_client.read_deployment(deployment_ids[0])
        assert result.name == "test_runner"

    def test_deploy_in_sync_context(
        self,
        sync_prefect_client: SyncPrefectClient,
        work_pool_with_image_variable,
        monkeypatch,
    ):
        monkeypatch.setattr("prefect.docker.docker_image.build_image", MagicMock())
        mock_docker = MagicMock()
        mock_docker.return_value.__enter__.return_value = mock_docker
        mock_docker.api.push.return_value = []
        monkeypatch.setattr("prefect.docker.docker_image.docker_client", mock_docker)
        monkeypatch.setattr(
            "prefect.docker.docker_image.generate_default_dockerfile", MagicMock()
        )

        deployment = RunnerDeployment.from_flow(
            dummy_flow_1, __file__, interval=3600, version_type=VersionType.SIMPLE
        )

        deployment_ids = deploy(
            deployment,
            work_pool_name=work_pool_with_image_variable.name,
            image="test-image",
        )

        result = sync_prefect_client.read_deployment(deployment_ids[0])
        assert result.name == "test_runner"


class TestRunnerAsyncDispatch:
    """Tests for Runner methods migrated from @sync_compatible to @async_dispatch.

    These tests verify the critical behavior from issue #15008 where
    @sync_compatible would incorrectly return coroutines in sync context
    (see issues #14712 and #14625).
    """

    def test_add_flow_in_sync_context(self, sync_prefect_client: SyncPrefectClient):
        """add_flow must return UUID (not coroutine) in sync context.

        This is the critical regression test for issues #14712 and #14625.
        """
        runner = Runner(name="test-sync-add-flow")

        result = runner.add_flow(dummy_flow_1)

        assert not isinstance(result, Coroutine), "sync context returned coroutine"
        assert isinstance(result, uuid.UUID)

        deployment = sync_prefect_client.read_deployment(result)
        assert deployment.name == "test-sync-add-flow"

    async def test_add_flow_in_async_context(self, prefect_client: PrefectClient):
        """add_flow should dispatch to async and return coroutine in async context."""
        runner = Runner(name="test-async-add-flow")

        result = runner.add_flow(dummy_flow_1)

        assert isinstance(result, Coroutine)
        deployment_id = await result

        deployment = await prefect_client.read_deployment(deployment_id)
        assert deployment.name == "test-async-add-flow"

    def test_add_deployment_in_sync_context(
        self, sync_prefect_client: SyncPrefectClient
    ):
        """add_deployment must return UUID (not coroutine) in sync context."""
        runner = Runner(name="test-sync-add-deployment")
        deployment = dummy_flow_1.to_deployment(name="sync-deployment-test", _sync=True)

        result = runner.add_deployment(deployment)

        assert not isinstance(result, Coroutine), "sync context returned coroutine"
        assert isinstance(result, uuid.UUID)

        fetched = sync_prefect_client.read_deployment(result)
        assert fetched.name == "sync-deployment-test"

    async def test_add_deployment_in_async_context(self, prefect_client: PrefectClient):
        """add_deployment should dispatch to async in async context."""
        runner = Runner(name="test-async-add-deployment")
        deployment = await dummy_flow_1.ato_deployment(name="async-deployment-test")

        result = runner.add_deployment(deployment)

        assert isinstance(result, Coroutine)
        deployment_id = await result

        fetched = await prefect_client.read_deployment(deployment_id)
        assert fetched.name == "async-deployment-test"

    def test_stop_not_started_raises_error(self):
        """stop raises RuntimeError when runner not started."""
        runner = Runner(name="test-stop-not-started")

        with pytest.raises(RuntimeError, match="not yet started"):
            runner.stop()

    async def test_stop_dispatches_to_async_in_async_context(self):
        """stop should dispatch to astop in async context."""
        runner = Runner(name="test-stop-dispatch")

        result = runner.stop()

        assert isinstance(result, Coroutine)
        with pytest.raises(RuntimeError, match="not yet started"):
            await result


class TestResolveStarter:
    """Regression tests for _resolve_starter routing."""

    async def test_add_flow_deployment_uses_direct_subprocess_starter(
        self, prefect_client: PrefectClient
    ):
        """Deployments registered via add_flow should use DirectSubprocessStarter,
        not EngineCommandStarter. This preserves the pre-refactor behavior where
        in-memory flows are run directly without spawning `python -m prefect.engine`.

        Regression test for the _resolve_starter routing logic.
        """
        from prefect.runner._starter_direct import DirectSubprocessStarter

        runner = Runner(name="test-direct-starter")
        deployment_id = await runner.add_flow(dummy_flow_1, __file__, interval=3600)

        async with runner:
            flow_run = await prefect_client.create_flow_run_from_deployment(
                deployment_id
            )
            starter = runner._scheduled_run_poller._resolve_starter(flow_run)
            assert isinstance(starter, DirectSubprocessStarter)

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_add_flow_runs_via_direct_subprocess(
        self, prefect_client: PrefectClient
    ):
        """End-to-end: add_flow deployment executes via run_flow_in_subprocess,
        not via `python -m prefect.engine`. Patches the direct starter module
        to prove the in-memory path is taken.
        """
        called = False

        def tracking_run_flow(*args, **kwargs):
            nonlocal called
            called = True
            return original_run_flow_in_subprocess(*args, **kwargs)

        runner = Runner()
        deployment_id = await runner.add_flow(dummy_flow_1, __file__, interval=3600)

        flow_run = await prefect_client.create_flow_run_from_deployment(deployment_id)

        with patch.object(
            starter_mod, "run_flow_in_subprocess", side_effect=tracking_run_flow
        ):
            await runner.start(run_once=True)

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert flow_run.state
        assert flow_run.state.is_completed()
        assert called, "run_flow_in_subprocess was not called — add_flow path is broken"

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_add_flow_preserves_failed_direct_subprocess_outcome(
        self,
        prefect_client: PrefectClient,
        caplog: pytest.LogCaptureFixture,
    ):
        @flow(on_crashed=[on_crashed])
        def failed_flow():
            raise ValueError("application failure")

        processes: list[Any] = []

        def tracking_run_flow(*args: Any, **kwargs: Any):
            process = original_run_flow_in_subprocess(*args, **kwargs)
            processes.append(process)
            return process

        runner = Runner()
        deployment_id = await runner.add_flow(failed_flow, __file__, interval=3600)
        flow_run = await prefect_client.create_flow_run_from_deployment(deployment_id)

        with patch.object(
            starter_mod,
            "run_flow_in_subprocess",
            side_effect=tracking_run_flow,
        ):
            infrastructure_result = await runner.start(run_once=True)

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert processes[0].exitcode == 0
        assert infrastructure_result is None
        assert flow_run.state is not None
        assert flow_run.state.is_failed()
        assert "This flow crashed!" not in caplog.text
        assert "Process exited with status code: 1" not in caplog.text

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_add_flow_preserves_direct_subprocess_crash_fallback(
        self,
        prefect_client: PrefectClient,
        caplog: pytest.LogCaptureFixture,
    ):
        @flow(on_crashed=[on_crashed])
        def crashed_flow():
            os._exit(7)

        processes: list[Any] = []

        def tracking_run_flow(*args: Any, **kwargs: Any):
            process = original_run_flow_in_subprocess(*args, **kwargs)
            processes.append(process)
            return process

        runner = Runner()
        deployment_id = await runner.add_flow(crashed_flow, __file__, interval=3600)
        flow_run = await prefect_client.create_flow_run_from_deployment(deployment_id)

        with patch.object(
            starter_mod,
            "run_flow_in_subprocess",
            side_effect=tracking_run_flow,
        ):
            await runner.start(run_once=True)

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert processes[0].exitcode == 7
        assert flow_run.state is not None
        assert flow_run.state.is_crashed()
        assert "This flow crashed!" in caplog.text
        assert "Process exited with status code: 7" in caplog.text

    async def test_storage_deployment_uses_engine_command_starter(
        self, prefect_client: PrefectClient
    ):
        """Deployments without an in-memory flow (e.g. from storage) should use
        EngineCommandStarter to spawn `python -m prefect.engine`.
        """
        from prefect.runner._starter_engine import EngineCommandStarter

        runner = Runner(name="test-engine-starter", pause_on_shutdown=False)

        async with runner:
            # Register a deployment ID without an associated flow object
            dep_id = uuid.uuid4()
            runner._deployment_registry.register_deployment(dep_id)

            flow_run = MagicMock(spec=FlowRun)
            flow_run.deployment_id = dep_id

            starter = runner._scheduled_run_poller._resolve_starter(flow_run)
            assert isinstance(starter, EngineCommandStarter)
