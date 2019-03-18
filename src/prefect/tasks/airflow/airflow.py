# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/beta-eula
"""
This module contains tasks for migrating Airflow workflows into Prefect. Using these requires `airflow` to be installed.

For more details, see [the Airflow conversion tutorial](../../guide/tutorials/airflow_migration.html).
"""

import os
import pickle
import sqlite3
import subprocess
import tempfile
import warnings
from collections import defaultdict
from contextlib import closing
from typing import Any, Dict, List

import prefect


__all__ = ["AirflowTask"]


def custom_query(db: str, query: str) -> List:
    with closing(sqlite3.connect(db)) as connection:
        with closing(connection.cursor()) as cursor:
            cursor.execute(query)
            return cursor.fetchall()


class AirflowTask(prefect.tasks.shell.ShellTask):
    """
    Task wrapper for executing individual Airflow tasks.

    Successful execution of this task requires a separate conda environment in which `airflow` is installed.
    Any XComs this task pushes will be converted to return values for this task.
    Unless certain CLI flags are provided (e.g., `-A`), execution of this task will respect Airflow trigger rules.

    Args:
        - task_id (string): the Airflow `task_id` to execute at runtime
        - dag_id (string): the Airflow `dag_id` containing the given `task_id`
        - airflow_env (str, optional): the name of the conda environment in which `airflow` is installed;
            defaults to `"airflow"`
        - cli_flags (List[str], optional): a list of CLI flags to provide to `airflow run` at runtime;
            see [the airflow docs](https://airflow.apache.org/cli.html#run) for options.  This can be used to ignore Airflow trigger rules
            by providing `cli_flags=['-A']`
        - env (dict, optional): dictionary of environment variables to use for
            the subprocess (e.g., )
        - execution_date (str, optional): the execution date for this task run; can also be provided to the run method;
            if not provided here or to `run()`, will be pulled from context
        - db_conn (str, optional): the location of the airflow database; currently only SQLite DBs are supported;
            defaults to `~/airflow/airflow.db`; used for pulling XComs and inspecting task states
        - **kwargs: additional keyword arguments to pass to the Task constructor

    Example:
        ```python
        from prefect import Flow
        from prefect.tasks.airflow import AirflowTask

        # compare with https://github.com/apache/airflow/blob/master/airflow/example_dags/example_xcom.py
        puller = AirflowTask(
            task_id="puller",
            dag_id="example_xcom",
            execution_date="1999-09-20",
        )
        push = AirflowTask(
            task_id="push",
            dag_id="example_xcom",
            execution_date="1999-09-20",
        )
        push_by_returning = AirflowTask(
            task_id="push_by_returning",
            dag_id="example_xcom",
            execution_date="1999-09-20",
        )

        with Flow(name="example_xcom") as flow:
            res = puller(upstream_tasks=[push, push_by_returning])

        flow_state = flow.run()

        # XComs auto-convert to return values
        assert flow_state.result[push].result == [1, 2, 3]
        assert flow_state.result[push_by_returning].result == {"a": "b"}
        ```
    """

    def __init__(
        self,
        task_id: str,
        dag_id: str,
        cli_flags: List[str] = None,
        airflow_env: str = "airflow",
        env: dict = None,
        execution_date: str = None,
        db_conn: str = None,
        **kwargs: Any
    ):
        if cli_flags is None:
            cli_flags = []
        cmd = "airflow run " + " ".join(cli_flags) + " {0} {1} {2}"
        self.db_conn = db_conn or os.path.expanduser("~/airflow/airflow.db")
        self.dag_id = dag_id
        self.task_id = task_id
        self.execution_date = execution_date
        kwargs.setdefault("name", task_id)
        super().__init__(
            command=cmd,
            env=env,
            helper_script="source deactivate && source activate {}".format(airflow_env),
            **kwargs
        )

    def _state_conversion(self, query: List) -> None:
        if query:
            status = query[0][0]
            if status == "skipped":
                raise prefect.engine.signals.SKIP(
                    "Airflow task state marked as 'skipped' in airflow db"
                )
            elif status != "success":
                raise prefect.engine.signals.FAIL(
                    "Airflow task state marked as {} in airflow db".format(
                        status.rstrip()
                    )
                )

    def _pre_check(self, execution_date: str) -> None:
        check_query = "select state from task_instance where task_id='{0}' and dag_id='{1}' and execution_date like '%{2}%'"
        status = custom_query(
            self.db_conn, check_query.format(self.task_id, self.dag_id, execution_date)
        )
        self._state_conversion(status)

    def _post_check(self, execution_date: str) -> None:
        check_query = "select state from task_instance where task_id='{0}' and dag_id='{1}' and execution_date like '%{2}%'"
        status = custom_query(
            self.db_conn, check_query.format(self.task_id, self.dag_id, execution_date)
        )
        if not status:
            raise prefect.engine.signals.SKIP(
                "Airflow task state not present in airflow db, was skipped."
            )
        self._state_conversion(status)

    def _pull_xcom(self, execution_date: str) -> Any:
        check_query = "select value from xcom where task_id='{0}' and dag_id='{1}' and execution_date like '%{2}%'"
        data = custom_query(
            self.db_conn, check_query.format(self.task_id, self.dag_id, execution_date)
        )
        if data:
            return pickle.loads(data[0][0])

    @prefect.utilities.tasks.defaults_from_attrs("execution_date")
    def run(self, execution_date: str = None) -> Any:  # type: ignore
        """
        Executes `airflow run` for the provided `task_id`, `dag_id` and `execution_date`.

        Args:
            - execution_date (str, optional): the execution date for this task run;
                if not provided here or at initialization, will be pulled from context

        Raises:
            - prefect.engine.signals.PrefectStateSignal: depending on the state of the task_instance in the Airflow DB

        Returns:
            - Any: any data this task pushes as an XCom
        """
        execution_date = prefect.context.get("execution_date", execution_date)
        self._pre_check(execution_date)
        self.command = self.command.format(  # type: ignore
            self.dag_id, self.task_id, execution_date
        )
        res = super().run()
        if "Task is not able to be run" in res.decode():
            raise prefect.engine.signals.SKIP("Airflow task was not run.")
        self._post_check(execution_date)
        data = self._pull_xcom(execution_date)
        return data
