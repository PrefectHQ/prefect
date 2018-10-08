import os
import pytest
import subprocess
import tempfile

airflow = pytest.importorskip("airflow")

from prefect.engine.state import Success, Skipped, Failed
from prefect.utilities.airflow_utils import AirFlow


@pytest.fixture(scope="module")
def airflow_db():
    with tempfile.NamedTemporaryFile(
        prefix="prefect-airflow", suffix="prefect-airflow-test.db"
    ) as tmp:
        env = os.environ.copy()
        env["AIRFLOW__CORE__SQL_ALCHEMY_CONN"] = "sqlite:///" + tmp.name
        status = subprocess.check_output(["bash", "-c", "airflow initdb"], env=env)
        yield tmp.name


@pytest.mark.airflow()
def test_airflow_accepts_existing_sqlite_db():
    flow = AirFlow(dag_id="example_bash_operator", db_file="test_doesnt_exist")
    assert (
        flow.env.get("AIRFLOW__CORE__SQL_ALCHEMY_CONN") == "sqlite:///test_doesnt_exist"
    )


@pytest.mark.airflow()
def test_airflow_creates_sqlite_db_if_none_provided():
    flow = AirFlow(dag_id="example_bash_operator")
    sql_conn = flow.env.get("AIRFLOW__CORE__SQL_ALCHEMY_CONN")
    assert sql_conn.startswith("sqlite:///")
    assert sql_conn.endswith("prefect-airflow.db")


@pytest.mark.airflow()
def test_example_branch_operator(airflow_db):
    flow = AirFlow(dag_id="example_branch_operator", db_file=airflow_db)
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


@pytest.mark.airflow()
def test_example_xcom(airflow_db):
    flow = AirFlow(dag_id="example_xcom", db_file=airflow_db)
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


@pytest.mark.airflow()
def test_example_short_circuit_operator(airflow_db):
    flow = AirFlow(dag_id="example_short_circuit_operator", db_file=airflow_db)
    res = flow.run(execution_date="2018-09-20", return_tasks=flow.tasks)
    assert res.is_successful()

    for task, state in res.result.items():
        if "condition" in task.name:
            assert isinstance(state, Success)
        elif "false" in task.name:
            assert isinstance(state, Skipped)
        elif "true" in task.name:
            assert isinstance(state, Success)


@pytest.mark.airflow()
def test_example_bash_operator(airflow_db):
    flow = AirFlow(dag_id="example_bash_operator", db_file=airflow_db)
    res = flow.run(execution_date="2018-09-20", return_tasks=flow.tasks)
    assert res.is_successful()

    for task, state in res.result.items():
        assert isinstance(state, Success)
