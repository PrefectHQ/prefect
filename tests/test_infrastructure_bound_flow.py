from __future__ import annotations

import base64
import inspect
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import ANY, MagicMock

import anyio.abc
import cloudpickle
import pytest
from pydantic import Field

from prefect._result_records import ResultRecord, ResultRecordMetadata
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.client.schemas.objects import (
    FlowRun,
    State,
    WorkPool,
    WorkPoolStorageConfiguration,
)
from prefect.context import FlowRunContext
from prefect.filesystems import LocalFileSystem, WritableFileSystem
from prefect.flows import (
    Flow,
    InfrastructureBoundFlow,
    bind_flow_to_infrastructure,
    flow,
)
from prefect.serializers import JSONSerializer, PickleSerializer
from prefect.settings import PREFECT_RESULTS_PERSIST_BY_DEFAULT
from prefect.settings.context import temporary_settings
from prefect.states import Completed
from prefect.task_runners import ThreadPoolTaskRunner
from prefect.workers.base import BaseJobConfiguration, BaseWorker, BaseWorkerResult
from prefect.workers.process import ProcessWorker


class FakeResultStorageBlock(WritableFileSystem):
    _block_type_slug = f"fake-result-storage-block-{uuid.uuid4()}"
    place: str = Field(default="test-place")

    async def read_path(self, path: str) -> bytes:
        return base64.b64encode(cloudpickle.dumps("Here you go chief!"))

    async def write_path(self, path: str, content: bytes) -> None:
        print("What do you expect me to do with this?")


class TestInfrastructureBoundFlow:
    @pytest.fixture(autouse=True)
    def mock_subprocess_check_call(self, monkeypatch: pytest.MonkeyPatch):
        mock = MagicMock()
        monkeypatch.setattr(subprocess, "check_call", mock)
        return mock

    @pytest.fixture
    def frozen_uuid(self, monkeypatch: pytest.MonkeyPatch):
        # Freeze the UUID to ensure the same value is used for the duration of the test
        frozen_uuid = uuid.uuid4()
        monkeypatch.setattr(uuid, "uuid4", lambda: frozen_uuid)
        return frozen_uuid

    @pytest.fixture
    async def work_pool(self, prefect_client: PrefectClient):
        UPLOAD_STEP = {
            "prefect_mock.experimental.bundles.upload": {
                "requires": "prefect-mock==0.5.5",
                "bucket": "test-bucket",
                "credentials_block_name": "my-creds",
            }
        }

        EXECUTE_STEP = {
            "prefect_mock.experimental.bundles.execute": {
                "requires": "prefect-mock==0.5.5",
                "bucket": "test-bucket",
                "credentials_block_name": "my-creds",
            }
        }

        result_storage_block = FakeResultStorageBlock(place="test-place")
        maybe_coro = result_storage_block.save(name="my-result-storage-block")
        if inspect.isawaitable(maybe_coro):
            block_document_id = await maybe_coro
        else:
            block_document_id = maybe_coro

        return await prefect_client.create_work_pool(
            WorkPoolCreate(
                name=f"submission-work-pool-{uuid.uuid4()}",
                type="process",
                base_job_template=ProcessWorker.get_default_base_job_template(),
                storage_configuration=WorkPoolStorageConfiguration(
                    bundle_upload_step=UPLOAD_STEP,
                    bundle_execution_step=EXECUTE_STEP,
                    default_result_storage_block_id=block_document_id,
                ),
            )
        )

    @pytest.fixture
    async def work_pool_missing_storage_configuration(
        self, prefect_client: PrefectClient
    ):
        return await prefect_client.create_work_pool(
            WorkPoolCreate(
                name=f"test-{uuid.uuid4()}",
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

        future = infrastructure_bound_flow.submit(x=1, y="not an int")  # pyright: ignore[reportArgumentType] wrong type for test
        with pytest.raises(TypeError):
            future.result()

    @pytest.mark.filterwarnings("ignore::FutureWarning")
    async def test_dispatch(
        self,
        work_pool: WorkPool,
        result_storage: LocalFileSystem,
        mock_subprocess_check_call: MagicMock,
        frozen_uuid: uuid.UUID,
        prefect_client: PrefectClient,
    ):
        python_version_info = sys.version_info

        @flow(
            result_storage=result_storage,
        )
        def my_flow(x: int, y: int):
            return x + y

        infrastructure_bound_flow = bind_flow_to_infrastructure(
            flow=my_flow, work_pool=work_pool.name, worker_cls=ProcessWorker
        )

        future = infrastructure_bound_flow.submit_to_work_pool(x=1, y=2)
        assert future.state.is_scheduled()
        expected_upload_command = [
            "uv",
            "run",
            "--quiet",
            "--with",
            "prefect-mock==0.5.5",
            "--python",
            f"{python_version_info.major}.{python_version_info.minor}",
            "-m",
            "prefect_mock.experimental.bundles.upload",
            "--bucket",
            "test-bucket",
            "--credentials-block-name",
            "my-creds",
            "--key",
            str(frozen_uuid),
            str(frozen_uuid),
        ]
        mock_subprocess_check_call.assert_called_once_with(
            expected_upload_command,
            cwd=ANY,
        )
        expected_execute_command = [
            "uv",
            "run",
            "--with",
            "prefect-mock==0.5.5",
            "--python",
            f"{python_version_info.major}.{python_version_info.minor}",
            "-m",
            "prefect_mock.experimental.bundles.execute",
            "--bucket",
            "test-bucket",
            "--credentials-block-name",
            "my-creds",
            "--key",
            str(frozen_uuid),
        ]
        flow_run = await prefect_client.read_flow_run(future.flow_run_id)
        assert flow_run.work_pool_name == work_pool.name
        assert flow_run.work_queue_name == "default"
        assert flow_run.job_variables == {"command": " ".join(expected_execute_command)}

    @pytest.mark.filterwarnings("ignore::FutureWarning")
    @pytest.mark.usefixtures("mock_subprocess_check_call")
    def test_dispatch_errors_on_work_pool_without_storage_configuration(
        self,
        work_pool_missing_storage_configuration: WorkPool,
        result_storage: LocalFileSystem,
    ):
        @flow(
            result_storage=result_storage,
        )
        def my_flow(x: int, y: int):
            return x + y

        infrastructure_bound_flow = bind_flow_to_infrastructure(
            flow=my_flow,
            work_pool=work_pool_missing_storage_configuration.name,
            worker_cls=ProcessWorker,
        )

        with pytest.raises(
            RuntimeError, match="Storage is not configured for work pool"
        ):
            infrastructure_bound_flow.submit_to_work_pool(x=1, y=2)

    @pytest.mark.filterwarnings("ignore::FutureWarning")
    @pytest.mark.usefixtures("mock_subprocess_check_call")
    async def test_dispatch_flow_from_within_flow(
        self,
        work_pool: WorkPool,
        prefect_client: PrefectClient,
    ):
        @flow
        def test_flow():
            print("It ain't much, but it's a living")

        infrastructure_bound_flow = bind_flow_to_infrastructure(
            flow=test_flow, work_pool=work_pool.name, worker_cls=ProcessWorker
        )

        @flow
        async def parent_flow():
            flow_run_ctx = FlowRunContext.get()
            future = infrastructure_bound_flow.submit_to_work_pool()
            flow_run = getattr(flow_run_ctx, "flow_run", None)
            flow_run_id = flow_run.id if flow_run else None
            return flow_run_id, future.flow_run_id

        parent_flow_run_id, child_flow_run_id = await parent_flow()
        assert parent_flow_run_id is not None
        parent_flow_run = await prefect_client.read_flow_run(parent_flow_run_id)
        child_flow_run = await prefect_client.read_flow_run(child_flow_run_id)
        assert child_flow_run.parent_task_run_id is not None
        parent_task_run = await prefect_client.read_task_run(
            child_flow_run.parent_task_run_id
        )  # pyright: ignore[reportArgumentType] wrong type for test
        assert child_flow_run.parent_task_run_id == parent_task_run.id
        assert parent_task_run.flow_run_id == parent_flow_run.id

    @pytest.mark.filterwarnings("ignore::FutureWarning")
    @pytest.mark.usefixtures("mock_subprocess_check_call")
    async def test_submit_uses_work_pool_result_storage_block(
        self,
        work_pool: WorkPool,
    ):
        class SubmitterOfUnpreparedFlows(
            BaseWorker[BaseJobConfiguration, Any, BaseWorkerResult]
        ):
            type = "submitter-of-unprepared-flows"
            job_configuration = BaseJobConfiguration

            async def run(
                self,
                flow_run: FlowRun,
                configuration: BaseJobConfiguration,
                task_status: anyio.abc.TaskStatus[int] | None = None,
            ):
                # Need to trick the client into saving the result record
                with temporary_settings({PREFECT_RESULTS_PERSIST_BY_DEFAULT: True}):
                    fake_state = Completed(
                        data=ResultRecord(
                            result="Totally legit result",
                            metadata=ResultRecordMetadata(
                                serializer=PickleSerializer(),
                                expiration=None,
                                storage_key="totally-legit-result",
                                storage_block_id=work_pool.storage_configuration.default_result_storage_block_id,
                            ),
                        )
                    )
                    await self.client.set_flow_run_state(
                        flow_run.id,
                        state=fake_state,
                        force=True,
                    )
                return BaseWorkerResult(identifier="test", status_code=0)

        @flow
        def unprepared_flow():
            print("Dang it, I forgot my result storage. Can I borrow yours?")

        infrastructure_bound_flow = bind_flow_to_infrastructure(
            flow=unprepared_flow, work_pool=work_pool.name, worker_cls=ProcessWorker
        )

        future = infrastructure_bound_flow.submit_to_work_pool()

        # Start the worker to pick up and "run" the flow
        await SubmitterOfUnpreparedFlows(work_pool_name=work_pool.name).start(
            run_once=True
        )

        # Return value is hardcoded in the FakeResultStorage to ensure it is used as expected
        assert future.result() == "Here you go chief!"
