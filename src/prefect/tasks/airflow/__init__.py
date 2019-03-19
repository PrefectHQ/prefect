"""
This module contains tasks that help migrate Airflow workflows into Prefect. Using these requires `airflow` to be installed in a separate conda environment.

Note that by default, external Airflow dependencies and triggers will be respected; these can be ignored by passing `-A` as a CLI flag to the `AirflowTask`.

For example, we can recreate the [example XCom DAG](https://github.com/apache/airflow/blob/master/airflow/example_dags/example_xcom.py), using
default settings:

```python
from prefect import Flow
from prefect.tasks.airflow import AirflowTask

puller = AirflowTask(
    task_id="puller",
    dag_id="example_xcom",
)
push = AirflowTask(
    task_id="push",
    dag_id="example_xcom",
)
push_by_returning = AirflowTask(
    task_id="push_by_returning",
    dag_id="example_xcom",
)

with Flow(name="example_xcom") as flow:
    res = puller(upstream_tasks=[push, push_by_returning])

flow_state = flow.run()

# XComs auto-convert to return values
assert flow_state.result[push].result == [1, 2, 3]
assert flow_state.result[push_by_returning].result == {"a": "b"}
```

Note the difference between how one can specify dependencies in Prefect vs. Airflow.
"""

from .airflow import AirflowTask, AirflowTriggerDAG
