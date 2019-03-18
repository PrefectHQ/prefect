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
    ignore flags
    """

    def __init__(
        self,
        task_id: str,
        dag_id: str,
        cli_flags: List[str] = None,
        airflow_env: str = "airflow",
        execution_date: str = None,
        db_conn: str = None,
        **kwargs: Any
    ):
        if cli_flags is None:
            cli_flags = []
        base_cmd = "airflow run ".format(" ".join(cli_flags))
        cmd = base_cmd + " {0} {1} {2}"
        self.db_conn = db_conn or os.path.expanduser("~/airflow/airflow.db")
        self.dag_id = dag_id
        self.task_id = task_id
        self.execution_date = execution_date
        kwargs.setdefault("name", task_id)
        super().__init__(
            command=cmd,
            helper_script="source deactivate && source activate {}".format(airflow_env),
            **kwargs
        )

    def pre_check(self, execution_date: str) -> None:
        check_query = "select state from task_instance where task_id='{0}' and dag_id='{1}' and execution_date like '%{2}%'"
        status = custom_query(
            self.db_conn, check_query.format(self.task_id, self.dag_id, execution_date)
        )
        if status and status[0][0] == "skipped":
            raise prefect.engine.signals.SKIP("Task marked as 'skipped' in airflow db")

    def post_check(self, execution_date: str) -> None:
        check_query = "select state from task_instance where task_id='{0}' and dag_id='{1}' and execution_date like '%{2}%'"
        query = custom_query(
            self.db_conn, check_query.format(self.task_id, self.dag_id, execution_date)
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

    def pull_xcom(self, execution_date: str) -> Any:
        check_query = "select value from xcom where task_id='{0}' and dag_id='{1}' and execution_date like '%{2}%'"
        data = custom_query(
            self.db_conn, check_query.format(self.task_id, self.dag_id, execution_date)
        )
        if data:
            return pickle.loads(data[0][0])

    @prefect.utilities.tasks.defaults_from_attrs("execution_date")
    def run(self, execution_date: str = None) -> Any:  # type: ignore
        execution_date = prefect.context.get("execution_date", execution_date)
        self.pre_check(execution_date)
        self.command = self.command.format(  # type: ignore
            self.dag_id, self.task_id, execution_date
        )
        res = super().run()
        if "Task is not able to be run" in res.decode():
            raise prefect.engine.signals.SKIP("Airflow task was not run.")
        self.post_check(execution_date)
        data = self.pull_xcom(execution_date)
        return data
