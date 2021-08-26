import pytest

from prefect import task, flow
from prefect.executors import SynchronousExecutor, DaskExecutor


def get_test_flow():
    @task
    def task_a():
        print("Inside task_a.fn")
        return "a"

    @task
    def task_b():
        return "b"

    @task
    def task_c(b):
        return b + "c"

    @flow(version="test")
    def test_flow():
        a = task_a()
        b = task_b()
        c = task_c(b)
        return a, b, c

    return test_flow


@pytest.mark.parametrize(
    "executor",
    [
        SynchronousExecutor(),
        DaskExecutor(),
    ],
)
def test_flow_run_by_executor(executor):
    test_flow = get_test_flow()
    test_flow.executor = executor

    future = test_flow()
    state = future.result()

    assert state.is_completed()
    return_data = state.data
    assert (return_data[0].data, return_data[1].data, return_data[2].data) == (
        "a",
        "b",
        "bc",
    )
