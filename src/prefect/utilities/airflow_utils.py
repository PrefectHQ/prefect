# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula
"""
This module contains utilities for migrating Airflow workflows into Prefect. Using these requires `airflow` to be installed.

For more details, see [the Airflow conversion tutorial](../../tutorials/airflow_migration.html).
"""

import sqlite3
import warnings
import os
import pickle
import subprocess
import tempfile

try:
    import airflow
except ImportError:
    # warning instead of Exception so generate_docs.py can work
    warnings.warn(
        "The airflow_utils conversion tools require `airflow` to be installed."
    )

from collections import defaultdict
from contextlib import closing
from typing import Dict, List, Any

import prefect


__all__ = ["AirFlow"]


def custom_query(db: str, query: str) -> List:
    with closing(sqlite3.connect(db)) as connection:
        with closing(connection.cursor()) as cursor:
            cursor.execute(query)
            return cursor.fetchall()


trigger_mapping = {
    "all_success": prefect.triggers.all_successful,
    "all_failed": prefect.triggers.all_failed,
    "all_done": prefect.triggers.all_finished,
    "one_success": prefect.triggers.any_successful,
    "one_failed": prefect.triggers.any_failed,
    "dummy": prefect.triggers.always_run,
}


class AirTask(prefect.tasks.shell.ShellTask):
    def __init__(self, task: "airflow.models.BaseOperator", **kwargs: Any) -> None:
        name = task.task_id
        dag_id = task.dag_id
        trigger = trigger_mapping[task.trigger_rule]
        cmd = "airflow run {0} {1} {2}"
        self.dag_id = dag_id
        self.task = task
        super().__init__(
            name=name,
            command=cmd,
            skip_on_upstream_skip=False,
            max_retries=task.retries,
            tags=task.pool,
            trigger=trigger,
            **kwargs
        )

    def pre_check(self, execution_date: str, airflow_env: dict) -> None:
        check_query = "select state from task_instance where task_id='{0}' and dag_id='{1}' and execution_date like '%{2}%'"
        dbfile = airflow_env["AIRFLOW__CORE__SQL_ALCHEMY_CONN"][
            10:
        ]  # removes sqlite:/// noise
        status = custom_query(
            dbfile, check_query.format(self.name, self.dag_id, execution_date)
        )
        if status and status[0][0] == "skipped":
            raise prefect.engine.signals.SKIP("Task marked as 'skipped' in airflow db")

    def post_check(self, execution_date: str, airflow_env: dict) -> None:
        check_query = "select state from task_instance where task_id='{0}' and dag_id='{1}' and execution_date like '%{2}%'"
        dbfile = airflow_env["AIRFLOW__CORE__SQL_ALCHEMY_CONN"][
            10:
        ]  # removes sqlite:/// noise
        query = custom_query(
            dbfile, check_query.format(self.name, self.dag_id, execution_date)
        )

        if query:
            status = query[0][0]
        else:
            raise prefect.engine.signals.SKIP(
                "Airflow task state not present in airflow db, was skipped."
            )
        if status == "skipped":
            raise prefect.engine.signals.SKIP(
                "Airflow task state marked as 'skipped' in airflow db"
            )
        elif status != "success":
            raise prefect.engine.signals.FAIL(
                "Airflow task state marked as {} in airflow db".format(status.rstrip())
            )

    def pull_xcom(self, execution_date: str, airflow_env: dict) -> Any:
        check_query = "select value from xcom where task_id='{0}' and dag_id='{1}' and execution_date like '%{2}%'"
        dbfile = airflow_env["AIRFLOW__CORE__SQL_ALCHEMY_CONN"][
            10:
        ]  # removes sqlite:/// noise
        data = custom_query(
            dbfile, check_query.format(self.name, self.dag_id, execution_date)
        )
        if data:
            return pickle.loads(data[0][0])

    def run(self) -> Any:  # type: ignore
        execution_date = prefect.context.get("execution_date", "")
        airflow_env = prefect.context.get("airflow_env", {})
        self.pre_check(execution_date, airflow_env)
        self.command = self.command.format(  # type: ignore
            self.dag_id, self.name, execution_date
        )
        res = super().run(env=airflow_env)
        if "Task is not able to be run" in res.decode():
            raise prefect.engine.signals.SKIP("Airflow task was not run.")
        self.post_check(execution_date, airflow_env)
        data = self.pull_xcom(execution_date, airflow_env)
        return data


class AirFlow(prefect.core.flow.Flow):
    """
    Subclass of Prefect Flow which represents a given Airflow DAG as a Prefect Flow.
    Upon initialization, each Airflow task will be represented by a corresponding Prefect task
    of the same name.

    Args:
        - dag_id (str): the `dag_id` of the Airflow DAG you wish to "import" as a Prefect Flow
        - *args (optional): additional arguments to be passed to the standard Flow init method
        - db_file (str, optional): the location of the sqlite3 Airflow database;
            defaults to creating a temporary one
        - dag_folder (str, optional): the location of the dag_folder on disk;
            defaults to your configured Airflow default
        - **kwargs (optional): additional keyword arguments to be passed to the standard Flow init method

    Example:
        ```python
        from prefect.utilities.airflow_utils import AirFlow

        flow = AirFlow(dag_id="example_bash_operator")
        flow.tasks
        # {<Task: also_run_this>,
        # <Task: run_after_loop>,
        # <Task: run_this_last>,
        # <Task: runme_0>,
        # <Task: runme_1>,
        # <Task: runme_2>}
        flow.visualize()
        ```
    """

    def __init__(
        self,
        dag_id: str,
        *args: Any,
        db_file: str = None,
        dag_folder: str = None,
        **kwargs: Any
    ) -> None:
        self.dag = airflow.models.DagBag(dag_folder=dag_folder).dags[dag_id]
        super().__init__(*args, **kwargs)
        self._populate_tasks()
        self.env = self._init_db(db_file=db_file, dag_folder=dag_folder)

    def _init_db(self, db_file: str = None, dag_folder: str = None) -> dict:
        env = os.environ.copy()
        if dag_folder is not None:
            env["AIRFLOW__CORE__DAGS_FOLDER"] = dag_folder
        if db_file is not None:
            env["AIRFLOW__CORE__SQL_ALCHEMY_CONN"] = "sqlite:///" + db_file
        else:
            self.td = tempfile.TemporaryDirectory(prefix="prefect-airflow")
            env["AIRFLOW__CORE__SQL_ALCHEMY_CONN"] = (
                "sqlite:///" + self.td.name + "/prefect-airflow.db"
            )
            status = subprocess.check_output(["bash", "-c", "airflow initdb"], env=env)
        return env

    def run(  # type: ignore
        self, execution_date: str, **kwargs: Any
    ) -> "prefect.engine.state.State":
        """
        The main entrypoint for executing the Flow / DAG.

        Args:
            - execution_date (str): an execution date to pass to Airflow for
                each task run
            - *kwargs: additional kwargs to pass to the
                standard Flow.run method

        Returns:
            - State: the Prefect State corresponding to the run of the Flow
        """
        with prefect.context(execution_date=execution_date, airflow_env=self.env):
            return super().run(**kwargs)

    def _issue_warnings(self, task: "airflow.models.BaseOperator") -> None:
        parameter_warning = False
        if task.params:
            warnings.warn(
                "Use of Airflow parameters detected; consider converting these to Prefect Parameters."
            )
        if task.pool:
            warnings.warn(
                "Use of Airflow pools detected; consider converting these to Prefect tags and using throttling."
            )

    def _populate_tasks(self) -> None:
        task_dict = {}  # type: Dict[str, Any]

        def to_task(t: "airflow.models.BaseOperator") -> AirTask:
            if t.task_id not in task_dict:
                task_dict[t.task_id] = AirTask(t)
            return task_dict[t.task_id]

        to_process = self.dag.roots  # airflow roots are actually leaves...
        while to_process:
            airtask = to_process.pop()
            self._issue_warnings(airtask)
            self.set_dependencies(
                task=to_task(airtask),
                upstream_tasks=[to_task(t) for t in airtask.upstream_list],
            )
            to_process += airtask.upstream_list
