import time
import pytest
import anyio

# Import the local 'tests' module to pickle to ray workers
from prefect.task_runners import ConcurrentTaskRunner, SequentialTaskRunner
from prefect.testing.standard_test_suites import TaskRunnerStandardTestSuite
from prefect import task, flow


@pytest.fixture
def default_sequential_task_runner():
    yield SequentialTaskRunner()


@pytest.fixture
def default_concurrent_task_runner():
    yield ConcurrentTaskRunner()


async def test_task_runner_cannot_be_started_while_running():
    async with SequentialTaskRunner().start() as task_runner:
        with pytest.raises(RuntimeError, match="already started"):
            async with task_runner.start():
                pass

class TestSequentialTaskRunner(TaskRunnerStandardTestSuite):
    @pytest.fixture
    def task_runner(self):
        yield SequentialTaskRunner()


class TestConcurrentTaskRunner(TaskRunnerStandardTestSuite):
    @pytest.fixture
    def task_runner(self):
        yield ConcurrentTaskRunner()

class TestConcurrentTaskRunnerLimitedThreads(TaskRunnerStandardTestSuite):
    @pytest.fixture
    def task_runner(self):
        yield ConcurrentTaskRunner(max_workers=3)

class TestConcurrentTaskRunnerSingleThreaded(TaskRunnerStandardTestSuite):
    @pytest.fixture
    def task_runner(self):
        yield ConcurrentTaskRunner(max_workers=1)

    def test_sync_tasks_run_sequentially_with_single_thread(
        self, task_runner, tmp_file
    ):
        @task
        def foo():
            time.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @task
        def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            foo()
            bar()

        test_flow()

        assert tmp_file.read_text() == "bar"

    async def test_async_tasks_run_sequentially_with_single_thread(
        self, task_runner, tmp_file
    ):
        @task
        async def foo():
            await anyio.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @task
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            await foo.submit()
            await bar.submit()

        await test_flow()

        assert tmp_file.read_text() == "bar"
