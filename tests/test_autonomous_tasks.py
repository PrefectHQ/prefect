import pytest

from prefect import Task, task
from prefect.client.schemas import TaskRun
from prefect.filesystems import LocalFileSystem
from prefect.results import ResultFactory
from prefect.server.api.task_runs import scheduled_task_runs_queue
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING,
    temporary_settings,
)
from prefect.utilities.asyncutils import sync_compatible


@sync_compatible
async def result_factory_from_task(task):
    return await ResultFactory.from_task(task)


@pytest.fixture
def local_filesystem():
    block = LocalFileSystem(basepath="~/.prefect/storage/test")
    block.save("test-fs", overwrite=True)
    return block


@pytest.fixture(autouse=True)
def allow_experimental_task_scheduling():
    with temporary_settings(
        {
            PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING: True,
            # PREFECT_DEFAULT_RESULT_STORAGE_BLOCK: "local-filesystem/test-fs",
        }
    ):
        yield


@pytest.fixture(autouse=True)
async def clear_scheduled_task_queues():
    queue = scheduled_task_runs_queue()
    while not queue.empty():
        queue.get_nowait()

    yield

    while not queue.empty():
        queue.get_nowait()


@pytest.fixture
def foo_task():
    @task
    def foo(x: int) -> int:
        print(x)
        return x

    return foo


@pytest.fixture
def async_foo_task():
    @task
    async def async_foo(x: int) -> int:
        print(x)
        return x

    return async_foo


@pytest.fixture
def foo_task_with_result_storage(foo_task, local_filesystem):
    return foo_task.with_options(result_storage=local_filesystem)


@pytest.fixture
def async_foo_task_with_result_storage(async_foo_task, local_filesystem):
    return async_foo_task.with_options(result_storage=local_filesystem)


def test_task_submission_fails_when_experimental_flag_off(foo_task):
    with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING: False}):
        with pytest.raises(RuntimeError, match="Tasks cannot be run outside of a flow"):
            foo_task.submit(42)


def test_task_submission_with_parameters_fails_without_result_storage(foo_task):
    foo_task_without_result_storage = foo_task.with_options(result_storage=None)
    task_run = foo_task_without_result_storage.submit(42)

    result_factory = result_factory_from_task(foo_task)

    with pytest.raises(AssertionError, match="Was it persisted?"):
        result_factory.read_parameters(task_run.state.state_details.task_parameters_id)


def test_task_submission_creates_a_scheduled_task_run(foo_task_with_result_storage):
    task_run = foo_task_with_result_storage.submit(42)
    assert task_run.state.is_scheduled()

    result_factory = result_factory_from_task(foo_task_with_result_storage)

    parameters = result_factory.read_parameters(
        task_run.state.state_details.task_parameters_id
    )

    assert parameters == dict(x=42)


async def test_async_task_submission_creates_a_scheduled_task_run(
    async_foo_task_with_result_storage,
):
    task_run = await async_foo_task_with_result_storage.submit(42)
    assert task_run.state.is_scheduled()

    result_factory = await result_factory_from_task(async_foo_task_with_result_storage)

    parameters = await result_factory.read_parameters(
        task_run.state.state_details.task_parameters_id
    )

    assert parameters == dict(x=42)


async def test_scheduled_tasks_are_enqueued_server_side(
    foo_task_with_result_storage: Task,
):
    task_run: TaskRun = await foo_task_with_result_storage.submit(42)
    assert task_run.state.is_scheduled()

    queue = scheduled_task_runs_queue()
    assert queue.qsize() == 1
    enqueued: TaskRun = queue.get_nowait()

    # The server-side task run through API-like serialization for comparison
    enqueued = TaskRun.parse_obj(enqueued.dict(json_compatible=True))

    assert enqueued == task_run
