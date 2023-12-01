import pytest

from prefect import task
from prefect.client.schemas.objects import TaskRunResult
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ALLOW_TASK_AUTONOMY,
    temporary_settings,
)
from prefect.tasks import task_input_hash
from prefect.utilities.asyncutils import sync_compatible


@pytest.fixture(autouse=True)
def allow_task_autonomy():
    with temporary_settings({PREFECT_EXPERIMENTAL_ALLOW_TASK_AUTONOMY: True}):
        yield


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
def read_task_run(prefect_client):
    @sync_compatible
    async def _read_task_run(task_run_id):
        return await prefect_client.read_task_run(task_run_id)

    return _read_task_run


class TestResults:
    def test_result_via_state(self, foo_task):
        state = foo_task(42, return_state=True)
        assert state.is_completed()
        assert state.result() == 42

    async def test_result_via_state_async(self, async_foo_task):
        state = await async_foo_task(42, return_state=True)
        assert state.is_completed()
        assert await state.result() == 42

    def test_result_via_submit(self, foo_task):
        result = foo_task.submit(42).result()
        assert result == 42

    async def test_result_via_submit_async(self, async_foo_task):
        result = await (await async_foo_task.submit(42)).result()
        assert result == 42

    def test_result_via_map(self, foo_task):
        results = foo_task.map([42, 43])
        assert [r.result() for r in results] == [42, 43]

    async def test_result_via_map_async(self, async_foo_task):
        results = await async_foo_task.map([42, 43])
        assert [await r.result() for r in results] == [42, 43]


class TestOptionsRespected:
    @pytest.fixture
    def foo_task_with_caching(self, foo_task):
        return foo_task.with_options(cache_key_fn=task_input_hash)

    @pytest.fixture
    def async_foo_task_with_caching(self, async_foo_task):
        return async_foo_task.with_options(cache_key_fn=task_input_hash)

    class TestLogPrints:
        def test_log_prints(self, foo_task, caplog):
            foo_task.with_options(log_prints=True)(42)
            assert "42" in caplog.text

        def test_log_prints_when_submitted(self, foo_task, caplog):
            foo_task.with_options(log_prints=True).submit(42)
            assert "42" in caplog.text

        def test_log_prints_when_mapped(self, foo_task, caplog):
            foo_task.with_options(log_prints=True).map([42, 43])
            assert "42" in caplog.text
            assert "43" in caplog.text

        async def test_log_prints_async(self, async_foo_task, caplog):
            await async_foo_task.with_options(log_prints=True)(42)
            assert "42" in caplog.text

        async def test_log_prints_when_submitted_async(self, async_foo_task, caplog):
            await async_foo_task.with_options(log_prints=True).submit(42)
            assert "42" in caplog.text

        async def test_log_prints_when_mapped_async(self, async_foo_task, caplog):
            await async_foo_task.with_options(log_prints=True).map([42, 43])
            assert "42" in caplog.text
            assert "43" in caplog.text

        class TestCaching:
            def test_caching(self, foo_task_with_caching):
                state = foo_task_with_caching(42, return_state=True)
                assert state.result() == 42
                assert state.is_completed()

                next_state = foo_task_with_caching(42, return_state=True)
                assert next_state.result() == 42
                assert next_state.name == "Cached"

            async def test_caching_async(self, async_foo_task_with_caching):
                state = await async_foo_task_with_caching(42, return_state=True)
                assert await state.result() == 42
                assert state.is_completed()

                next_state = await async_foo_task_with_caching(42, return_state=True)
                assert (await next_state.result()) == 42
                assert next_state.name == "Cached"

            def test_caching_when_submitted(self, foo_task_with_caching):
                state = foo_task_with_caching.submit(42, return_state=True)
                assert state.result() == 42
                assert state.is_completed()

                next_state = foo_task_with_caching.submit(42, return_state=True)
                assert next_state.result() == 42
                assert next_state.name == "Cached"

            async def test_caching_when_submitted_async(
                self, async_foo_task_with_caching
            ):
                state = await async_foo_task_with_caching.submit(42, return_state=True)
                assert await state.result() == 42
                assert state.is_completed()

                next_state = await async_foo_task_with_caching.submit(
                    42, return_state=True
                )
                assert await next_state.result() == 42
                assert next_state.name == "Cached"

            def test_caching_when_mapped(self, foo_task_with_caching):
                results = foo_task_with_caching.map([42, 43], return_state=True)
                assert [s.result() for s in results] == [42, 43]

                next_results = foo_task_with_caching.map([42, 43], return_state=True)
                assert [s.result() for s in next_results] == [42, 43]

                assert [s.name for s in next_results] == ["Cached"] * 2

            async def test_caching_when_mapped_async(self, async_foo_task_with_caching):
                results = await async_foo_task_with_caching.map(
                    [42, 43], return_state=True
                )

                assert [await s.result() for s in results] == [42, 43]

                next_results = await async_foo_task_with_caching.map(
                    [42, 43], return_state=True
                )
                assert [await s.result() for s in next_results] == [42, 43]

                assert [s.name for s in next_results] == ["Cached"] * 2

    class TestRetries:
        def test_retries(self):
            task_run_count = 0

            @task
            def slow_starter(x: int) -> int:
                nonlocal task_run_count
                task_run_count += 1
                if task_run_count == 1:
                    raise ValueError("oops")
                return x

            bad_task_with_retries = slow_starter.with_options(retries=1)
            state = bad_task_with_retries(42, return_state=True)
            assert state.is_completed()
            assert state.result() == 42
            assert task_run_count == 2

        async def test_retries_async(self):
            task_run_count = 0

            @task
            async def async_slow_starter(x: int) -> int:
                nonlocal task_run_count
                task_run_count += 1
                if task_run_count == 1:
                    raise ValueError("oops")
                return x

            async_bad_task_with_retries = async_slow_starter.with_options(retries=1)

            state = await async_bad_task_with_retries(42, return_state=True)
            assert state.is_completed()
            assert await state.result() == 42
            assert task_run_count == 2

        def test_retries_when_submitted(self):
            task_run_count = 0

            @task
            def slow_starter(x: int) -> int:
                nonlocal task_run_count
                task_run_count += 1
                if task_run_count == 1:
                    raise ValueError("oops")
                return x

            bad_task_with_retries = slow_starter.with_options(retries=1)

            state = bad_task_with_retries.submit(42, return_state=True)
            assert state.is_completed()
            assert state.result() == 42
            assert task_run_count == 2

        async def test_retries_when_submitted_async(self):
            task_run_count = 0

            @task
            async def async_slow_starter(x: int) -> int:
                nonlocal task_run_count
                task_run_count += 1
                if task_run_count == 1:
                    raise ValueError("oops")
                return x

            async_bad_task_with_retries = async_slow_starter.with_options(retries=1)

            state = await async_bad_task_with_retries.submit(42, return_state=True)
            assert state.is_completed()
            assert await state.result() == 42
            assert task_run_count == 2

        def test_retries_when_mapped(self):
            task_run_count = 0

            @task
            def slow_starter(x: int) -> int:
                nonlocal task_run_count
                task_run_count += 1
                if task_run_count == 1:
                    raise ValueError("oops")
                return x

            bad_task_with_retries = slow_starter.with_options(retries=1)

            results = bad_task_with_retries.map([42, 43], return_state=True)
            assert [s.result() for s in results] == [42, 43]
            assert [s.name for s in results] == ["Completed"] * 2
            assert task_run_count == 3

        async def test_retries_when_mapped_async(self):
            task_run_count = 0

            @task
            async def async_slow_starter(x: int) -> int:
                nonlocal task_run_count
                task_run_count += 1
                if task_run_count == 1:
                    raise ValueError("oops")
                return x

            async_bad_task_with_retries = async_slow_starter.with_options(retries=1)

            results = await async_bad_task_with_retries.map([42, 43], return_state=True)
            assert [await s.result() for s in results] == [42, 43]
            assert [s.name for s in results] == ["Completed"] * 2
            assert task_run_count == 3


class TestWaitFor:
    def test_wait_for(self, foo_task):
        state = foo_task(42, return_state=True)

        other_state = foo_task(43, wait_for=[state], return_state=True)

        assert state.is_completed()
        assert other_state.is_completed()

        assert state.result() == 42
        assert other_state.result() == 43

    async def test_wait_for_async(self, async_foo_task):
        state = await async_foo_task(42, return_state=True)

        other_state = await async_foo_task(43, wait_for=[state], return_state=True)

        assert state.is_completed()
        assert other_state.is_completed()

        assert await state.result() == 42
        assert await other_state.result() == 43

    def test_wait_for_when_submitted(self, foo_task):
        state = foo_task.submit(42, return_state=True)

        other_state = foo_task.submit(43, wait_for=[state], return_state=True)

        assert state.is_completed()
        assert other_state.is_completed()

        assert state.result() == 42
        assert other_state.result() == 43

    async def test_wait_for_when_submitted_async(self, async_foo_task):
        state = await async_foo_task.submit(42, return_state=True)

        other_state = await async_foo_task.submit(
            43, wait_for=[state], return_state=True
        )

        assert state.is_completed()
        assert other_state.is_completed()

        assert await state.result() == 42
        assert await other_state.result() == 43

    def test_wait_for_when_mapped(self, foo_task):
        state = foo_task.map([42, 43], return_state=True)

        other_state = foo_task.map([44, 45], wait_for=[state], return_state=True)

        assert [s.result() for s in state] == [42, 43]
        assert [s.result() for s in other_state] == [44, 45]

        assert [s.name for s in state] == ["Completed"] * 2
        assert [s.name for s in other_state] == ["Completed"] * 2

    async def test_wait_for_when_mapped_async(self, async_foo_task):
        state = await async_foo_task.map([42, 43], return_state=True)

        other_state = await async_foo_task.map(
            [44, 45], wait_for=[state], return_state=True
        )

        assert [await s.result() for s in state] == [42, 43]
        assert [await s.result() for s in other_state] == [44, 45]

        assert [s.name for s in state] == ["Completed"] * 2
        assert [s.name for s in other_state] == ["Completed"] * 2

    @pytest.mark.xfail(reason="TODO")
    def test_task_inputs_includes_wait_for_tasks(self, foo_task, read_task_run):
        a = foo_task.submit(1, return_state=True)
        b = foo_task.submit(2, return_state=True)
        c = foo_task.submit(3, wait_for=[a, b], return_state=True)

        c_task_run = read_task_run(c.state_details.task_run_id)

        assert c_task_run.task_inputs["x"] == [
            TaskRunResult(id=c.state_details.task_run_id)
        ], "Data passing inputs are preserved"

        assert set(c_task_run.task_inputs["wait_for"]) == {
            TaskRunResult(id=a.state_details.task_run_id),
            TaskRunResult(id=b.state_details.task_run_id),
        }, "'wait_for' included as a key with upstreams"

        assert set(c_task_run.task_inputs.keys()) == {
            "x",
            "wait_for",
        }, "No extra keys around"
