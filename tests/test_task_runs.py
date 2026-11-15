import asyncio
import uuid

import pytest

from prefect import task
from prefect.server.events.pipeline import EventsPipeline
from prefect.task_engine import run_task_async
from prefect.task_runs import TaskRunWaiter


class TestTaskRunWaiter:
    @pytest.fixture(autouse=True)
    def teardown(self):
        yield

        TaskRunWaiter.instance().stop()

    def test_instance_returns_singleton(self):
        assert TaskRunWaiter.instance() is TaskRunWaiter.instance()

    def test_instance_returns_instance_after_stop(self):
        instance = TaskRunWaiter.instance()
        instance.stop()
        assert TaskRunWaiter.instance() is not instance

    @pytest.mark.timeout(20)
    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_wait_for_task_run(self, prefect_client, emitting_events_pipeline):
        """This test will fail with a timeout error if waiting is not working correctly."""

        @task
        async def test_task():
            await asyncio.sleep(1)

        task_run_id = uuid.uuid4()
        asyncio.create_task(run_task_async(task=test_task, task_run_id=task_run_id))

        await TaskRunWaiter.wait_for_task_run(task_run_id)

        await emitting_events_pipeline.process_events()

        task_run = await prefect_client.read_task_run(task_run_id)
        assert task_run.state.is_completed()

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_wait_for_task_run_with_timeout(self):
        @task
        async def test_task():
            await asyncio.sleep(5)

        task_run_id = uuid.uuid4()
        run = asyncio.create_task(
            run_task_async(task=test_task, task_run_id=task_run_id)
        )

        await TaskRunWaiter.wait_for_task_run(task_run_id, timeout=1)

        # TaskRunWaiter stopped waiting before the task finished
        assert not run.done()
        await run

    @pytest.mark.timeout(20)
    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_wait_for_task_run_in_cached_state(
        self, emitting_events_pipeline: EventsPipeline
    ):
        """
        A cached task run finishes in a `Cached` state, so its final event is
        `prefect.task-run.Cached`. Regression test for
        https://github.com/PrefectHQ/prefect/issues/15427
        """
        cache_key = str(uuid.uuid4())

        @task(cache_key_fn=lambda *args, **kwargs: cache_key, persist_result=True)
        async def test_task() -> int:
            return 42

        await run_task_async(task=test_task)

        task_run_id = uuid.uuid4()
        await run_task_async(task=test_task, task_run_id=task_run_id)
        # Store the events so the waiter receives them when it subscribes
        await emitting_events_pipeline.process_events()

        state = await TaskRunWaiter.wait_for_task_run(task_run_id)

        assert state is not None
        assert state.is_completed()
        assert state.name == "Cached"

    @pytest.mark.timeout(20)
    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_non_singleton_mode(self, prefect_client, emitting_events_pipeline):
        waiter = TaskRunWaiter()
        assert waiter is not TaskRunWaiter.instance()

        @task
        async def test_task():
            await asyncio.sleep(1)

        task_run_id = uuid.uuid4()
        asyncio.create_task(run_task_async(task=test_task, task_run_id=task_run_id))

        await waiter.wait_for_task_run(task_run_id)

        await emitting_events_pipeline.process_events()

        task_run = await prefect_client.read_task_run(task_run_id)
        assert task_run.state.is_completed()

        waiter.stop()

    @pytest.mark.timeout(20)
    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_handles_concurrent_task_runs(
        self, prefect_client, emitting_events_pipeline
    ):
        @task
        async def fast_task():
            await asyncio.sleep(1)

        @task
        async def slow_task():
            await asyncio.sleep(5)

        task_run_id_1 = uuid.uuid4()
        task_run_id_2 = uuid.uuid4()

        asyncio.create_task(run_task_async(task=fast_task, task_run_id=task_run_id_1))
        asyncio.create_task(run_task_async(task=slow_task, task_run_id=task_run_id_2))

        await TaskRunWaiter.wait_for_task_run(task_run_id_1)

        await emitting_events_pipeline.process_events()

        task_run_1 = await prefect_client.read_task_run(task_run_id_1)
        task_run_2 = await prefect_client.read_task_run(task_run_id_2)

        assert task_run_1.state.is_completed()
        assert not task_run_2.state.is_completed()

        await TaskRunWaiter.wait_for_task_run(task_run_id_2)

        await emitting_events_pipeline.process_events()

        task_run_1 = await prefect_client.read_task_run(task_run_id_1)
        task_run_2 = await prefect_client.read_task_run(task_run_id_2)

        assert task_run_1.state.is_completed()
        assert task_run_2.state.is_completed()
