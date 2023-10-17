import pytest

from prefect import task


class TestTaskOptionsRespectedByAutonomousTasks:
    @pytest.fixture
    def foo_task(self):
        @task
        def foo(x: int) -> int:
            print(x)
            return x
        return foo
    @pytest.fixture
    def async_foo_task(self):
        @task
        async def async_foo(x: int) -> int:
            print(x)
            return x
        return async_foo
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
    
    
    class TestResults:
        def test_result_via_state(self, foo_task):
            state = foo_task(42, return_state=True)
            assert state.is_completed()
            assert state.result() == 42