import pytest
from unittest.mock import MagicMock

from prefect import flow
from prefect.tasks import task
from prefect.futures import PrefectFuture
from prefect.client import OrionClient


class TestTaskCall:
    def test_task_called_outside_flow_raises(self):
        @task
        def foo():
            pass

        with pytest.raises(
            RuntimeError, match="Tasks cannot be called outside of a flow"
        ):
            foo()

    def test_task_called_inside_flow(self):
        @task
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1)
            # Returns a future so we can run assertions outside of the flow context

        flow_future = bar()
        task_future = flow_future.result().data
        assert isinstance(task_future, PrefectFuture)
        assert task_future.result().data == 1

    @pytest.mark.parametrize("error", [ValueError("Hello"), None])
    def test_state_reflects_result_of_run(self, error):
        @task
        def bar():
            if error:
                raise error

        @flow(version="test")
        def foo():
            return bar()

        flow_future = foo()
        task_future = flow_future.result().data
        state = task_future.result()

        # Assert the final state is correct
        assert state.is_failed() if error else state.is_completed()
        assert state.data is error

    def test_task_runs_correctly_populate_dynamic_keys(self):
        @task
        def bar():
            return "foo"

        @flow(version="test")
        def foo():
            return bar(), bar()

        flow_future = foo()
        task_futures = [item for item in flow_future.result().data]

        orion_client = OrionClient()
        task_runs = [
            orion_client.read_task_run(task_run.run_id) for task_run in task_futures
        ]

        # Assert dynamic key is set correctly
        assert task_runs[0].dynamic_key == "0"
        assert task_runs[1].dynamic_key == "1"

    def test_task_called_with_task_dependency(self):
        @task
        def foo(x):
            return x

        @task
        def bar(y):
            return y + 1

        @flow
        def test_flow():
            return bar(foo(1))

        flow_future = test_flow()
        task_future = flow_future.result().data
        assert task_future.result().data == 2

    @pytest.mark.parametrize("always_fail", [True, False])
    def test_task_respects_retry_count(self, always_fail):
        mock = MagicMock()
        exc = ValueError()

        @task(max_retries=3)
        def flaky_function():
            mock()

            # 3 retries means 4 attempts
            # Succeed on the final retry unless we're ending in a failure
            if not always_fail and mock.call_count == 4:
                return True

            raise exc

        @flow
        def test_flow():
            return flaky_function()

        flow_future = test_flow()
        task_future = flow_future.result().data

        if always_fail:
            state = task_future.result()
            assert state.is_failed()
            assert state.data is exc
            assert mock.call_count == 4
        else:
            state = task_future.result()
            assert state.is_completed()
            assert state.data is True
            assert mock.call_count == 4

        client = OrionClient()
        states = client.read_task_run_states(task_future.run_id)
        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "Awaiting Retry",
            "Running",
            "Awaiting Retry",
            "Running",
            "Awaiting Retry",
            "Running",
            "Failed" if always_fail else "Completed",
        ]

    def test_task_only_uses_necessary_retries(self):
        mock = MagicMock()
        exc = ValueError()

        @task(max_retries=3)
        def flaky_function():
            mock()
            if mock.call_count == 2:
                return True
            raise exc

        @flow
        def test_flow():
            return flaky_function()

        flow_future = test_flow()
        task_future = flow_future.result().data

        state = task_future.result()
        assert state.is_completed()
        assert state.data is True
        assert mock.call_count == 2

        client = OrionClient()
        states = client.read_task_run_states(task_future.run_id)
        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "Awaiting Retry",
            "Running",
            "Completed",
        ]

    def test_task_respects_retry_delay(self, monkeypatch):
        mock = MagicMock()
        sleep = MagicMock()  # Mock sleep for fast testing
        monkeypatch.setattr("time.sleep", sleep)

        @task(max_retries=1, retry_delay_seconds=43)
        def flaky_function():
            mock()

            if mock.call_count == 2:
                return True

            raise ValueError("try again, but only once")

        @flow
        def test_flow():
            return flaky_function()

        flow_future = test_flow()
        task_future = flow_future.result().data

        assert sleep.call_count == 1
        # due to rounding, the expected sleep time will be less than 43 seconds
        # we test for a 3-second window to account for delays in CI
        assert 40 < sleep.call_args[0][0] < 43

        client = OrionClient()
        states = client.read_task_run_states(task_future.run_id)
        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "Awaiting Retry",
            "Running",
            "Completed",
        ]
