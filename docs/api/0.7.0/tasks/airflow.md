---
sidebarDepth: 2
editLink: false
---
# Airflow Tasks
---
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
 ## AirflowTask
 <div class='class-sig' id='prefect-tasks-airflow-airflow-airflowtask'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.airflow.airflow.AirflowTask</p>(task_id, dag_id, cli_flags=None, airflow_env="airflow", env=None, execution_date=None, db_conn=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/airflow/airflow.py#L23">[source]</a></span></div>

Task wrapper for executing individual Airflow tasks.

Successful execution of this task requires a separate conda environment in which `airflow` is installed. Any XComs this task pushes will be converted to return values for this task. Unless certain CLI flags are provided (e.g., `-A`), execution of this task will respect Airflow trigger rules.

**Args**:     <ul class="args"><li class="args">`task_id (string)`: the Airflow `task_id` to execute at runtime     </li><li class="args">`dag_id (string)`: the Airflow `dag_id` containing the given `task_id`     </li><li class="args">`airflow_env (str, optional)`: the name of the conda environment in which `airflow` is installed;         defaults to `"airflow"`     </li><li class="args">`cli_flags (List[str], optional)`: a list of CLI flags to provide to `airflow run` at runtime;         see [the airflow docs](https://airflow.apache.org/cli.html#run) for options.  This can be used to ignore Airflow trigger rules         by providing `cli_flags=['-A']`     </li><li class="args">`env (dict, optional)`: dictionary of environment variables to use for         the subprocess (e.g., `AIRFLOW__CORE__DAGS_FOLDER`)     </li><li class="args">`execution_date (str, optional)`: the execution date for this task run; can also be provided to the run method;         if not provided here or to `run()`, the value of `today` in context will be used     </li><li class="args">`db_conn (str, optional)`: the location of the airflow database; currently only SQLite DBs are supported;         defaults to `~/airflow/airflow.db`; used for pulling XComs and inspecting task states     </li><li class="args">`**kwargs`: additional keyword arguments to pass to the Task constructor</li></ul>**Example**:     
```python
    from prefect import Flow
    from prefect.tasks.airflow import AirflowTask

    # compare with https://github.com/apache/airflow/blob/master/airflow/example_dags/example_xcom.py
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

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-airflow-airflow-airflowtask-run'><p class="prefect-class">prefect.tasks.airflow.airflow.AirflowTask.run</p>(execution_date=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/airflow/airflow.py#L155">[source]</a></span></div>
<p class="methods">Executes `airflow run` for the provided `task_id`, `dag_id` and `execution_date`.<br><br>**Args**:     <ul class="args"><li class="args">`execution_date (str, optional)`: the execution date for this task run;         if not provided here or at initialization, the value of `today` in context will be used</li></ul>**Raises**:     <ul class="args"><li class="args">`prefect.engine.signals.PrefectStateSignal`: depending on the state of the task_instance in the Airflow DB</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: any data this task pushes as an XCom</li></ul></p>|

---
<br>

 ## AirflowTriggerDAG
 <div class='class-sig' id='prefect-tasks-airflow-airflow-airflowtriggerdag'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.airflow.airflow.AirflowTriggerDAG</p>(dag_id, airflow_env="airflow", execution_date=None, cli_flags=None, env=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/airflow/airflow.py#L185">[source]</a></span></div>

Task wrapper for triggering an Airflow DAG run.

Successful execution of this task requires a separate conda environment in which `airflow` is installed.

**Args**:     <ul class="args"><li class="args">`dag_id (string)`: the Airflow `dag_id` containing the given `task_id`     </li><li class="args">`airflow_env (str, optional)`: the name of the conda environment in which `airflow` is installed;         defaults to `"airflow"`     </li><li class="args">`execution_date (str, optional)`: the execution date for this task run; can also be provided to the run method;         if not provided here or to `run()`, the value of `today` in context will be used     </li><li class="args">`cli_flags (List[str], optional)`: a list of CLI flags to provide to `airflow trigger_dag` at runtime;         this can be used to provide `execution_date` via `["-e 1999-01-01"]`.  For a complete list of available options,         see the [corresponding Airflow documentation](https://airflow.apache.org/cli.html#trigger_dag)     </li><li class="args">`env (dict, optional)`: dictionary of environment variables to use for         the subprocess (e.g., `AIRFLOW__CORE__DAGS_FOLDER`)     </li><li class="args">`**kwargs`: additional keyword arguments to pass to the Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-airflow-airflow-airflowtriggerdag-run'><p class="prefect-class">prefect.tasks.airflow.airflow.AirflowTriggerDAG.run</p>(execution_date=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/airflow/airflow.py#L226">[source]</a></span></div>
<p class="methods">Executes `airflow trigger_dag` for the provided `dag_id` with the provided options.<br><br>**Args**:     <ul class="args"><li class="args">`execution_date (str, optional)`: the execution date for this task run;         if not provided here or at initialization, the value of `today` in context will be used</li></ul>**Raises**:     <ul class="args"><li class="args">`prefect.engine.signals.PrefectStateSignal`: depending on the state of the task_instance in the Airflow DB</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: any data this task pushes as an XCom</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on October 29, 2019 at 19:43 UTC</p>