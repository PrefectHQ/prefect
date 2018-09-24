import airflow
import sqlite3
import warnings
import os
import pickle
import subprocess
import tempfile

from collections import defaultdict
from contextlib import closing

import prefect


trigger_mapping = {
    "all_success": prefect.triggers.all_successful,
    "all_failed": prefect.triggers.all_failed,
    "all_done": prefect.triggers.all_finished,
    "one_success": prefect.triggers.any_successful,
    "one_failed": prefect.triggers.any_failed,
    "dummy": prefect.triggers.always_run,
}


def custom_query(db, query):
    with closing(sqlite3.connect(db)) as connection:
        with closing(connection.cursor()) as cursor:
            cursor.execute(query)
            return cursor.fetchall()


class AirTask(prefect.tasks.shell.ShellTask):
    def __init__(self, task, **kwargs):
        name = task.task_id
        dag_id = task.dag_id
        trigger = trigger_mapping[task.trigger_rule]
        cmd = "airflow run {0} {1} !execution_date".format(dag_id, name)
        self.dag_id = dag_id
        self.task = task
        super().__init__(
            name=name,
            command=cmd,
            trigger=trigger,
            skip_on_upstream_skip=False,
            max_retries=task.retries,
            tags=task.pool,
            **kwargs
        )

    def pre_check(self, execution_date, airflow_env):
        check_cmd = "airflow task_state {0} {1} {2} | tail -1".format(
            self.dag_id, self.name, execution_date
        )
        status = subprocess.check_output(["bash", "-c", check_cmd], env=airflow_env)
        if status.decode().rstrip() == "skipped":
            raise prefect.engine.signals.SKIP("Task marked as 'skipped' in airflow db")

    def post_check(self, execution_date, airflow_env):
        check_query = "select state from task_instance where task_id='{0}' and dag_id='{1}' and execution_date like '%{2}%'"
        dbfile = airflow_env.get("AIRFLOW__CORE__SQL_ALCHEMY_CONN")[10:] # removes sqlite:/// noise
        status = custom_query(dbfile, check_query.format(self.name,
                                                         self.dag_id,
                                                         execution_date))[0][0]

        if status == "None":
            raise prefect.engine.signals.DONTRUN(
                "Airflow task state marked as 'None' in airflow db"
            )
        if status == "skipped":
            raise prefect.engine.signals.SKIP(
                "Airflow task state marked as 'skipped' in airflow db"
            )
        elif status != "success":
            raise prefect.engine.signals.FAIL(
                "Airflow task state marked as {} in airflow db".format(
                    status.decode().rstrip()
                )
            )

    def pull_xcom(self, execution_date, airflow_env):
        check_query = "select value from xcom where task_id='{0}' and dag_id='{1}' and execution_date like '%{2}%'"
        dbfile = airflow_env.get("AIRFLOW__CORE__SQL_ALCHEMY_CONN")[10:] # removes sqlite:/// noise
        data = custom_query(dbfile, check_query.format(self.name,
                                                         self.dag_id,
                                                         execution_date))
        if data:
            return pickle.loads(data[0][0])

    def run(self):
        execution_date = prefect.context.get("_execution_date")
        airflow_env = prefect.context.get("_airflow_env")
        self.pre_check(execution_date, airflow_env)
        self.command = self.command.replace("!execution_date", execution_date)
        res = super().run(env=airflow_env)
        self.post_check(execution_date, airflow_env)
        data = self.pull_xcom(execution_date, airflow_env)
        return data


class AirFlow(prefect.core.flow.Flow):
    def __init__(self, dag_id, *args, **kwargs):
        self.dag = airflow.models.DagBag().dags[dag_id]
        super().__init__(*args, **kwargs)
        self.populate_tasks()
        self.env = self.init_db()

    def init_db(self):
        self.td = tempfile.TemporaryDirectory(prefix="prefect-airflow")
        env = os.environ.copy()
        env["AIRFLOW__CORE__SQL_ALCHEMY_CONN"] = (
            "sqlite:///" + self.td.name + "/prefect-airflow.db"
        )
        status = subprocess.check_output(["bash", "-c", "airflow initdb"], env=env)
        return env

    def run(self, execution_date, *args, **kwargs):
        with prefect.context(_execution_date=execution_date, _airflow_env=self.env):
            return super().run(*args, **kwargs)

    def issue_warnings(self, task):
        parameter_warning = False
        if task.params:
            warnings.warn(
                "Use of Airflow parameters detected; consider converting these to Prefect Parameters."
            )
        if task.pool:
            warnings.warn(
                "Use of Airflow pools detected; consider converting these to Prefect tags and using throttling."
            )

    def populate_tasks(self):
        task_dict = {}

        def to_task(t):
            if t.task_id not in task_dict:
                task_dict[t.task_id] = AirTask(t)
            return task_dict[t.task_id]

        to_process = self.dag.roots  # airflow roots are actually leaves...
        while to_process:
            airtask = to_process.pop()
            self.issue_warnings(airtask)
            self.set_dependencies(
                task=to_task(airtask),
                upstream_tasks=[to_task(t) for t in airtask.upstream_list],
            )
            to_process += airtask.upstream_list
