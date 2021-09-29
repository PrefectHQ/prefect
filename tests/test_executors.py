import pytest

from prefect import flow, task
from prefect.executors import DaskExecutor, LocalExecutor


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
        LocalExecutor(),
        DaskExecutor(),
    ],
)
def test_flow_run_by_executor(executor):
    test_flow = get_test_flow()
    test_flow.executor = executor

    a, b, c = test_flow().result
    assert (a.result, b.result, c.result) == (
        "a",
        "b",
        "bc",
    )
