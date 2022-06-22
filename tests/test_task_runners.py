import pytest

# Import the local 'tests' module to pickle to ray workers
from prefect.task_runners import ConcurrentTaskRunner, SequentialTaskRunner
from prefect.testing.standard_test_suites import TaskRunnerStandardTestSuite


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
