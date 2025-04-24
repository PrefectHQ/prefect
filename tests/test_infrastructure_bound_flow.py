import os
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.client.schemas.objects import FlowRun, State, WorkPool
from prefect.filesystems import LocalFileSystem
from prefect.flows import (
    Flow,
    InfrastructureBoundFlow,
    bind_flow_to_infrastructure,
    flow,
)
from prefect.serializers import JSONSerializer
from prefect.task_runners import ThreadPoolTaskRunner
from prefect.workers.process import ProcessWorker


class TestInfrastructureBoundFlow:
    @pytest.fixture
    async def work_pool(self, prefect_client: PrefectClient):
        return await prefect_client.create_work_pool(
            WorkPoolCreate(
                name=f"submission-work-pool-{uuid.uuid4()}",
                type="process",
                base_job_template=ProcessWorker.get_default_base_job_template(),
            )
        )

    @pytest.fixture
    def result_storage(self, tmp_path: Path):
        result_storage = LocalFileSystem(basepath=str(tmp_path / "result_storage"))
        result_storage.save(str(uuid.uuid4()))
        return result_storage

    def test_bind_flow_to_infrastructure(
        self, work_pool: WorkPool, result_storage: LocalFileSystem
    ):
        @flow(
            name="chicago-style",
            version="test",
            flow_run_name="test-run",
            retries=3,
            retry_delay_seconds=1,
            description="A flow with everything on it",
            timeout_seconds=100,
            validate_parameters=False,
            persist_result=True,
            result_storage=result_storage,
            result_serializer=JSONSerializer(),
            cache_result_in_memory=False,
            log_prints=True,
        )
        def dragged_through_the_garden():
            return "The works"

        @dragged_through_the_garden.on_completion
        def on_completion(flow: Flow[Any, str], flow_run: FlowRun, state: State):  # pyright: ignore[reportUnusedFunction]
            print(f"Flow run {flow_run.id} completed with state {state}")

        @dragged_through_the_garden.on_failure
        def on_failure(flow: Flow[Any, str], flow_run: FlowRun, state: State):  # pyright: ignore[reportUnusedFunction]
            print(f"Flow run {flow_run.id} failed with state {state}")

        @dragged_through_the_garden.on_cancellation
        def on_cancellation(flow: Flow[Any, str], flow_run: FlowRun, state: State):  # pyright: ignore[reportUnusedFunction]
            print(f"Flow run {flow_run.id} cancelled with state {state}")

        @dragged_through_the_garden.on_crashed
        def on_crashed(flow: Flow[Any, str], flow_run: FlowRun, state: State):  # pyright: ignore[reportUnusedFunction]
            print(f"Flow run {flow_run.id} crashed with state {state}")

        @dragged_through_the_garden.on_running
        def on_running(flow: Flow[Any, str], flow_run: FlowRun, state: State):  # pyright: ignore[reportUnusedFunction]
            print(f"Flow run {flow_run.id} is running with state {state}")

        infrastructure_bound_flow = bind_flow_to_infrastructure(
            flow=dragged_through_the_garden,
            work_pool=work_pool.name,
            worker_cls=ProcessWorker,
            job_variables={"key": "value"},
        )

        assert isinstance(infrastructure_bound_flow, InfrastructureBoundFlow)
        assert infrastructure_bound_flow.work_pool == work_pool.name
        assert infrastructure_bound_flow.job_variables == {"key": "value"}
        assert infrastructure_bound_flow.worker_cls == ProcessWorker

        # check that all flow attributes are copied over
        assert infrastructure_bound_flow.name == "chicago-style"
        assert infrastructure_bound_flow.version == "test"
        assert infrastructure_bound_flow.flow_run_name == "test-run"
        assert infrastructure_bound_flow.retries == 3
        assert infrastructure_bound_flow.retry_delay_seconds == 1
        assert infrastructure_bound_flow.description == "A flow with everything on it"
        assert infrastructure_bound_flow.result_storage == result_storage
        assert infrastructure_bound_flow.result_serializer == JSONSerializer()
        assert infrastructure_bound_flow.cache_result_in_memory is False
        assert infrastructure_bound_flow.log_prints is True
        assert infrastructure_bound_flow.timeout_seconds == 100
        assert infrastructure_bound_flow.should_validate_parameters is False
        assert infrastructure_bound_flow.persist_result is True
        assert infrastructure_bound_flow.on_completion_hooks == [on_completion]
        assert infrastructure_bound_flow.on_failure_hooks == [on_failure]
        assert infrastructure_bound_flow.on_cancellation_hooks == [on_cancellation]
        assert infrastructure_bound_flow.on_crashed_hooks == [on_crashed]
        assert infrastructure_bound_flow.on_running_hooks == [on_running]
        assert (
            infrastructure_bound_flow.task_runner
            == ThreadPoolTaskRunner()  # this one is implicit
        )

    def test_with_options(self, work_pool: WorkPool, result_storage: LocalFileSystem):
        on_mock = MagicMock()

        @flow(
            result_storage=result_storage,
        )
        def hello_world():
            return "Hello, world!"

        infrastructure_bound_flow = bind_flow_to_infrastructure(
            flow=hello_world, work_pool=work_pool.name, worker_cls=ProcessWorker
        )

        infrastructure_bound_flow = infrastructure_bound_flow.with_options(
            name="new-name",
            description="new-description",
            flow_run_name="new-flow-run-name",
            retries=10,
            retry_delay_seconds=1,
            timeout_seconds=100,
            validate_parameters=True,
            persist_result=False,
            result_storage=result_storage,
            result_serializer=JSONSerializer(),
            cache_result_in_memory=True,
            log_prints=False,
            on_completion=[on_mock],
            on_failure=[on_mock],
            on_cancellation=[on_mock],
            on_crashed=[on_mock],
            on_running=[on_mock],
            job_variables={"key": "value"},
        )

        assert infrastructure_bound_flow.name == "new-name"
        assert infrastructure_bound_flow.description == "new-description"
        assert infrastructure_bound_flow.flow_run_name == "new-flow-run-name"
        assert infrastructure_bound_flow.retries == 10
        assert infrastructure_bound_flow.retry_delay_seconds == 1
        assert infrastructure_bound_flow.timeout_seconds == 100
        assert infrastructure_bound_flow.should_validate_parameters is True
        assert infrastructure_bound_flow.persist_result is False
        assert infrastructure_bound_flow.result_storage == result_storage
        assert infrastructure_bound_flow.result_serializer == JSONSerializer()
        assert infrastructure_bound_flow.cache_result_in_memory is True
        assert infrastructure_bound_flow.log_prints is False
        assert infrastructure_bound_flow.on_completion_hooks == [on_mock]
        assert infrastructure_bound_flow.on_failure_hooks == [on_mock]
        assert infrastructure_bound_flow.on_cancellation_hooks == [on_mock]
        assert infrastructure_bound_flow.on_crashed_hooks == [on_mock]
        assert infrastructure_bound_flow.on_running_hooks == [on_mock]
        assert infrastructure_bound_flow.job_variables == {"key": "value"}

    @pytest.mark.filterwarnings("ignore::FutureWarning")
    def test_basic_call(self, work_pool: WorkPool, result_storage: LocalFileSystem):
        @flow(
            result_storage=result_storage,
        )
        def hello_world():
            return "Hello, world!"

        infrastructure_bound_flow = bind_flow_to_infrastructure(
            flow=hello_world, work_pool=work_pool.name, worker_cls=ProcessWorker
        )

        assert infrastructure_bound_flow() == "Hello, world!"

    @pytest.mark.filterwarnings("ignore::FutureWarning")
    async def test_async_call(
        self, work_pool: WorkPool, result_storage: LocalFileSystem
    ):
        @flow(
            result_storage=result_storage,
        )
        async def hello_world():
            return "Hello, world!"

        infrastructure_bound_flow = bind_flow_to_infrastructure(
            flow=hello_world, work_pool=work_pool.name, worker_cls=ProcessWorker
        )

        assert await infrastructure_bound_flow() == "Hello, world!"

    @pytest.mark.filterwarnings("ignore::FutureWarning")
    def test_call_with_parameters(
        self, work_pool: WorkPool, result_storage: LocalFileSystem
    ):
        @flow(
            result_storage=result_storage,
        )
        def hello_world(name: str):
            return f"Hello, {name}!"

        infrastructure_bound_flow = bind_flow_to_infrastructure(
            flow=hello_world, work_pool=work_pool.name, worker_cls=ProcessWorker
        )

        assert infrastructure_bound_flow("friend") == "Hello, friend!"

    @pytest.mark.filterwarnings("ignore::FutureWarning")
    def test_call_with_job_variables(
        self, work_pool: WorkPool, result_storage: LocalFileSystem, tmp_path: Path
    ):
        @flow(
            result_storage=result_storage,
        )
        def tell_me_your_cwd_and_env():
            return {
                "cwd": os.getcwd(),
                "env": os.environ.get("TEST_ENV_VAR"),
            }

        infrastructure_bound_flow = bind_flow_to_infrastructure(
            flow=tell_me_your_cwd_and_env,
            work_pool=work_pool.name,
            worker_cls=ProcessWorker,
            job_variables={
                "working_dir": str(tmp_path),
                "env": {"TEST_ENV_VAR": "TEST_VALUE"},
            },
        )

        assert infrastructure_bound_flow() == {
            "cwd": str(tmp_path),
            "env": "TEST_VALUE",
        }

    @pytest.mark.filterwarnings("ignore::FutureWarning")
    def test_call_with_return_state(
        self, work_pool: WorkPool, result_storage: LocalFileSystem
    ):
        @flow(
            result_storage=result_storage,
        )
        def hello_world():
            return "Hello, world!"

        infrastructure_bound_flow = bind_flow_to_infrastructure(
            flow=hello_world, work_pool=work_pool.name, worker_cls=ProcessWorker
        )

        result = infrastructure_bound_flow(return_state=True)
        assert result.is_completed()
        assert result.result() == "Hello, world!"

    @pytest.mark.filterwarnings("ignore::FutureWarning")
    def test_submit(self, work_pool: WorkPool, result_storage: LocalFileSystem):
        @flow(
            result_storage=result_storage,
        )
        def my_flow(x: int, y: int):
            return x + y

        infrastructure_bound_flow = bind_flow_to_infrastructure(
            flow=my_flow, work_pool=work_pool.name, worker_cls=ProcessWorker
        )

        future = infrastructure_bound_flow.submit(x=1, y=2)
        assert future.result() == 3

    @pytest.mark.filterwarnings("ignore::FutureWarning")
    def test_submit_with_error(
        self, work_pool: WorkPool, result_storage: LocalFileSystem
    ):
        @flow(
            result_storage=result_storage,
            validate_parameters=False,
        )
        def my_flow(x: int, y: int):
            return x + y

        infrastructure_bound_flow = bind_flow_to_infrastructure(
            flow=my_flow, work_pool=work_pool.name, worker_cls=ProcessWorker
        )

        future = infrastructure_bound_flow.submit(x=1, y="not an int")
        with pytest.raises(TypeError):
            future.result()
