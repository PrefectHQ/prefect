import pytest

from prefect import flow, task
from prefect.exceptions import IncompleteUpstreamTaskError
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

    a, b, c = test_flow().result()
    assert (a.result(), b.result(), c.result()) == (
        "a",
        "b",
        "bc",
    )


def get_failing_test_flow():
    @task
    def task_a():
        raise RuntimeError("This task fails!")

    @task
    def task_b():
        raise ValueError("This task fails and passes data downstream!")

    @task
    def task_c(b):
        # This task attempts to use the upstream data and should fail too
        return b + "c"

    @flow(version="test")
    def test_flow():
        a = task_a()
        b = task_b()
        c = task_c(b)
        d = task_c(c)
        return a, b, c, d

    return test_flow


@pytest.mark.parametrize(
    "executor",
    [
        LocalExecutor(),
        DaskExecutor(),
    ],
)
def test_failing_flow_run_by_executor(executor):
    test_flow = get_failing_test_flow()
    test_flow.executor = executor

    state = test_flow()
    assert state.is_failed()
    a, b, c, d = state.result(raise_on_failure=False)
    with pytest.raises(RuntimeError, match="This task fails!"):
        a.result()
    with pytest.raises(ValueError, match="This task fails and passes data downstream"):
        b.result()

    assert c.is_pending()
    assert c.name == "NotReady"
    assert (
        f"Upstream task '{b.state_details.task_run_id}' did not complete" in c.message
    )

    assert d.is_pending()
    assert d.name == "NotReady"
    assert (
        f"Upstream task '{c.state_details.task_run_id}' did not complete" in d.message
    )
