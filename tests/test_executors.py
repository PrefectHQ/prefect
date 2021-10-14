import pytest

from prefect import flow, task
from prefect.executors import DaskExecutor, SequentialExecutor
from prefect.context import get_run_context


@pytest.mark.parametrize(
    "executor",
    [
        SequentialExecutor(),
        DaskExecutor(),
    ],
)
def test_flow_run_by_executor(executor):
    @task
    def task_a():
        return "a"

    @task
    def task_b():
        return "b"

    @task
    def task_c(b):
        return b + "c"

    @flow(version="test", executor=executor)
    def test_flow():
        a = task_a()
        b = task_b()
        c = task_c(b)
        return a, b, c

    a, b, c = test_flow().result()
    assert (a.result(), b.result(), c.result()) == (
        "a",
        "b",
        "bc",
    )


@pytest.mark.parametrize(
    "executor",
    [
        SequentialExecutor(),
        DaskExecutor(),
    ],
)
def test_failing_flow_run_by_executor(executor):
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

    @flow(version="test", executor=executor)
    def test_flow():
        a = task_a()
        b = task_b()
        c = task_c(b)
        d = task_c(c)
        return a, b, c, d

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
        f"Upstream task run '{b.state_details.task_run_id}' did not reach a 'COMPLETED' state"
        in c.message
    )

    assert d.is_pending()
    assert d.name == "NotReady"
    assert (
        f"Upstream task run '{c.state_details.task_run_id}' did not reach a 'COMPLETED' state"
        in d.message
    )


@pytest.mark.parametrize(
    "parent_executor,child_executor",
    [
        (SequentialExecutor(), DaskExecutor()),
        (DaskExecutor(), SequentialExecutor()),
    ],
)
def test_subflow_run_by_executor(parent_executor, child_executor):
    @task
    def task_a():
        return "a"

    @task
    def task_b():
        return "b"

    @task
    def task_c(b):
        return b + "c"

    @flow(version="test", executor=parent_executor)
    def parent_flow():
        assert get_run_context().executor is parent_executor
        a = task_a()
        b = task_b()
        c = task_c(b)
        d = child_flow(c)
        return a, b, c, d

    @flow(version="test", executor=child_executor)
    def child_flow(c):
        assert get_run_context().executor is child_executor
        a = task_a()
        b = task_b()
        c = task_c(b)
        d = task_c(c)
        return a, b, c, d

    a, b, c, d = parent_flow().result()
    # parent
    assert (a.result(), b.result(), c.result()) == (
        "a",
        "b",
        "bc",
    )
    # child
    a, b, c, d = d.result()
    assert (a.result(), b.result(), c.result(), d.result()) == ("a", "b", "bc", "bcc")
