import os
import subprocess
import tempfile

import pytest

from prefect import Flow, Task, task, triggers
from prefect.tasks.airflow import AirflowTask, AirflowTriggerDAG
from prefect.tasks.shell import ShellTask

pytestmark = pytest.mark.airflow


@pytest.fixture(scope="module")
def airflow_settings():
    with tempfile.NamedTemporaryFile(
        prefix="prefect-airflow", suffix="prefect-airflow-test.db"
    ) as tmp:
        env = os.environ.copy()
        env["AIRFLOW__CORE__SQL_ALCHEMY_CONN"] = "sqlite:///" + tmp.name
        env["db_conn"] = tmp.name
        dag_folder = os.path.join(os.path.dirname(__file__), "dags")
        env["AIRFLOW__CORE__DAGS_FOLDER"] = dag_folder
        status = subprocess.check_output(
            [
                "bash",
                "-c",
                "source deactivate && source activate airflow && airflow initdb",
            ],
            env=env,
        )
        yield {
            k: v for k, v in env.items() if k.startswith("AIRFLOW") or k == "db_conn"
        }


class TestTaskStructure:
    def test_init_requires_task_and_dag_id(self):
        with pytest.raises(TypeError):
            task = AirflowTask()

        with pytest.raises(TypeError):
            task = AirflowTask(task_id="task name")

        with pytest.raises(TypeError):
            task = AirflowTask(dag_id="dag name")

    def test_name_defaults_to_task_id_but_can_be_changed(self):
        t1 = AirflowTask(task_id="test-task", dag_id="blob")
        assert t1.name == "test-task"

        t2 = AirflowTask(task_id="test-task", dag_id="blob", name="unique")
        assert t2.name == "unique"

    def test_command_responds_to_env_name(self):
        t1 = AirflowTask(task_id="test-task", dag_id="blob")
        assert t1.helper_script == "source deactivate && source activate airflow"

        t2 = AirflowTask(
            task_id="test-task", dag_id="blob", airflow_env="airflow_conda_env"
        )
        assert (
            t2.helper_script == "source deactivate && source activate airflow_conda_env"
        )

    def test_command_responds_to_cli_flags(self):
        t1 = AirflowTask(task_id="test-task", dag_id="blob", cli_flags=["--force"])
        assert t1.command.startswith("airflow run --force")


class TestSingleTaskRuns:
    def test_airflow_task_successfully_runs_a_task(self, airflow_settings):
        task = AirflowTask(
            db_conn=airflow_settings["db_conn"],
            task_id="also_run_this",
            dag_id="example_bash_operator",
            env=airflow_settings,
        )

        flow = Flow(name="test single task", tasks=[task])
        flow_state = flow.run()

        assert flow_state.is_successful()
        assert flow_state.result[task].is_successful()
        assert flow_state.result[task].result is None

    def test_airflow_task_uses_its_own_trigger_rules_by_default(self, airflow_settings):
        task = AirflowTask(
            db_conn=airflow_settings["db_conn"],
            task_id="run_this_last",
            dag_id="example_bash_operator",
            env=airflow_settings,
        )

        with Flow(name="test single task") as flow:
            res = task(execution_date="2011-01-01")
        flow_state = flow.run()

        assert flow_state.is_successful()
        assert flow_state.result[res].is_skipped()

    def test_airflow_task_uses_cli_flags(self, airflow_settings):
        task = AirflowTask(
            db_conn=airflow_settings["db_conn"],
            task_id="run_this_last",
            dag_id="example_bash_operator",
            cli_flags=["-A"],
            env=airflow_settings,
        )

        with Flow(name="test single task") as flow:
            res = task(execution_date="2011-01-02")
        flow_state = flow.run()

        assert flow_state.is_successful()
        assert flow_state.result[res].is_successful()
        assert not flow_state.result[res].is_skipped()
        assert flow_state.result[res].result is None

    def test_airflow_task_checks_db_state_prior_to_execution(self, airflow_settings):
        pass

    def test_airflow_task_converts_xcoms_to_return_values(self, airflow_settings):
        puller = AirflowTask(
            db_conn=airflow_settings["db_conn"],
            task_id="puller",
            dag_id="example_xcom",
            env=airflow_settings,
            execution_date="1999-09-20",
        )
        push = AirflowTask(
            db_conn=airflow_settings["db_conn"],
            task_id="push",
            dag_id="example_xcom",
            env=airflow_settings,
            execution_date="1999-09-20",
        )
        push_by_returning = AirflowTask(
            db_conn=airflow_settings["db_conn"],
            task_id="push_by_returning",
            dag_id="example_xcom",
            env=airflow_settings,
            execution_date="1999-09-20",
        )

        with Flow(name="xcom") as flow:
            res = puller(upstream_tasks=[push, push_by_returning])

        flow_state = flow.run()
        assert flow_state.is_successful()

        # puller
        assert flow_state.result[res].is_successful()
        assert flow_state.result[res].result is None

        # push
        assert flow_state.result[push].is_successful()
        assert flow_state.result[push].result == [1, 2, 3]

        # push_by_returning
        assert flow_state.result[push_by_returning].is_successful()
        assert flow_state.result[push_by_returning].result == {"a": "b"}


class TestTriggerDAG:
    def test_basic_trigger_dag_triggers(self, airflow_settings):
        task = AirflowTriggerDAG(
            dag_id="tutorial", execution_date="1986-09-20", env=airflow_settings
        )
        check_task = ShellTask(
            command="airflow list_dag_runs tutorial",
            helper_script=task.helper_script,
            env=airflow_settings,
        )

        with Flow(name="tutorial") as flow:
            res = check_task(upstream_tasks=[task])

        flow_state = flow.run()
        assert flow_state.is_successful()

        check_state = flow_state.result[res]
        assert check_state.is_successful()

        # check CLI output
        assert "manual__1986-09-20T00:00:00+00:00" in check_state.result
        assert "running" in check_state.result
        assert "1986-09-20T00:00:00+00:00" in check_state.result
