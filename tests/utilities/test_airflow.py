import pytest

try:
    import airflow
except ImportError:
    pytest.skip(reason="Airflow not installed.")

from prefect.engine.state import Success, Skipped, Failed
from prefect.utilities.airflow_utils import AirFlow


def test_example_branch_operator():
    flow = AirFlow(dag_id="example_branch_operator")
    res = flow.run(execution_date="2018-09-20", return_tasks=flow.tasks)
    assert res.is_successful()

    branch_tasks, follow_tasks = [], []
    for task, state in res.result.items():
        if task.name in ["run_this_first", "branching", "join"]:
            assert state.is_successful()
            assert state.result is None
        elif "follow" in task.name:
            follow_tasks.append((task, state))
        elif "branch" in task.name:
            branch_tasks.append((task, state))

    run_branches = list(filter(lambda x: not isinstance(x[1], Skipped), branch_tasks))
    assert len(run_branches) == 1
    branch, state = run_branches.pop()
    assert state.is_successful()
    assert all([isinstance(s, Skipped) for t, s in branch_tasks if t != branch])
    assert all(
        [isinstance(s, Skipped) for t, s in follow_tasks if (branch.name not in t.name)]
    )
    assert all(
        [isinstance(s, Success) for t, s in follow_tasks if (branch.name in t.name)]
    )


def test_example_xcom():
    flow = AirFlow(dag_id="example_xcom")
    res = flow.run(execution_date="2018-09-20", return_tasks=flow.tasks)
    assert res.is_successful()

    for task, state in res.result.items():
        if task.name == "puller":
            assert state.is_successful()
            assert state.result is None
        elif task.name == "push":
            assert state.is_successful()
            assert state.result == [1, 2, 3]
        if task.name == "push_by_returning":
            assert state.is_successful()
            assert state.result == {"a": "b"}


def test_example_short_circuit_operator():
    flow = AirFlow(dag_id="example_short_circuit_operator")
    res = flow.run(execution_date="2018-09-20", return_tasks=flow.tasks)
    assert res.is_successful()

    for task, state in res.result.items():
        if "condition" in task.name:
            assert isinstance(state, Success)
        elif "false" in task.name:
            assert isinstance(state, Skipped)
        elif "true" in task.name:
            assert isinstance(state, Success)


def test_example_bash_operator():
    flow = AirFlow(dag_id="example_bash_operator")
    res = flow.run(execution_date="2018-09-20", return_tasks=flow.tasks)
    assert res.is_successful()

    for task, state in res.result.items():
        assert isinstance(state, Success)
