import pytest

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
        task_future = flow_future.result()
        assert isinstance(task_future, PrefectFuture)
        assert task_future.result() == 1

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
        task_future = flow_future.result()

        raised = None
        try:
            task_future.result()
        except Exception as exc:
            raised = exc

        # Assert the exception was raised correctly
        assert raised is error

        # Assert the final state is correct
        states = OrionClient().read_task_run_states(task_future.run_id)
        final_state = states[-1]
        assert final_state.is_failed() if error else final_state.is_completed()

    def test_task_runs_correctly_populate_dynamic_keys(self):
        @task
        def bar():
            return "foo"

        @flow(version="test")
        def foo():
            return bar(), bar()

        flow_future = foo()
        task_futures = [item for item in flow_future.result()]

        orion_client = OrionClient()
        task_runs = [
            orion_client.read_task_run(task_run.run_id) for task_run in task_futures
        ]

        # Assert dynamic key is set correctly
        assert task_runs[0].dynamic_key == "0"
        assert task_runs[1].dynamic_key == "1"
