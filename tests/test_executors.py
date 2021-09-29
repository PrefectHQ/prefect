import pytest

from prefect import flow, task, get_result
from prefect.executors import DaskExecutor, SequentialExecutor


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
        SequentialExecutor(),
        DaskExecutor(),
    ],
)
def test_flow_run_by_executor(executor):
    test_flow = get_test_flow()
    test_flow.executor = executor

    task_states = get_result(test_flow())
    assert (
        get_result(task_states[0]),
        get_result(task_states[1]),
        get_result(task_states[2]),
    ) == (
        "a",
        "b",
        "bc",
    )
