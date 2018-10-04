# Airflow Conversion Tool

## Overview

Prefect is actively building out support for migrating workflows from Airflow to Prefect.  The current version of this functionality is not meant for production use cases _yet_; instead it is intended to be a proof-of-concept which whets your appetite for the possibilities, and demonstrates how easy it could be to migrate.

::: tip Be the change
**We are still actively soliciting feedback for any features or touch-ups that would be necessary in order for this tool to be production ready!**  <a href="mailto:hello@prefect.io?subject=Migrating from Airflow">Please reach out if you have a use case or feedback</a>.
:::

The utility presented here introspects a given Airflow DAG and creates a corresponding Prefect Flow object (called an `AirFlow`, pardon the pun) which _represents_ the underlying Airflow DAG.  Each Airflow operator of the DAG is represented by a corresponding Prefect task of the same name. Moreover, all dependency information is transferred to and handled by Prefect (triggers, skips, etc.).  During execution, each Prefect task runs its corresponding Airflow operator. This allows users to augment their Flow with new Prefect tasks, as well as taking advantage of Prefect functionality, all without giving up Airflow-specific operators and functions.

::: warning There are a few additional implementation details you should be aware of:
- In order to leave your Airflow DAGs unaffected, each `AirFlow` flow will spin up its own temporary sqlite3 database
- each task in your DAG will be mapped to a corresponding Prefect task which can be inspected with Prefect; the underlying Airflow task is still present under the hood, but **Prefect controls all execution logic**.  This is important because it highlights what is and isn't possible with the current tool:
    - any parallelism or resource pooling settings in Airflow will need to be explicitly set with Prefect
    - if you remove or replace a Prefect Airflow task, Airflow will still reference it and expect it to be run for its downstream dependencies
    - all triggers are converted automatically
- XComs pushed from a task are converted to the _return value_ for the corresponding Prefect task, because Prefect allows for data to be passed downstream
:::

These are subject to change per customer feedback!

## Example Airflow DAG
To see this functionality at work, let's begin with a contrived DAG meant to highlight the various features and benefits you might find by allowing Prefect to run your Airflow DAG.  Moreover, this exercise will highlight many of the differences between Airflow and Prefect.

::: tip Roadmap of our example DAG
- `run_this_first`: a dummy operator
- `branching`: a `BranchPythonOperator` which will randomly return one of `"branch_a"` or `"branch_b"`
    - `branch_a`: a dummy operator immediately downstream of `branching`
        - `push_xcom_for_branch_a`: downstream of `branch_a`; if run, pushes an XCom value of `"branch_a"`
    - `branch_b`: a dummy operator immediately downstream of `branching`
        - `push_xcom_for_branch_b`: downstream of `branch_b`; if run, pushes an XCom value of `"branch_b"`
- `join`: a final dummy operator which is downstream of the `push_xcom` tasks; will run as long as at least one of those is successful
:::

The following code is _pure Airflow_ which you should save in a `.py` file in your DAG folder and run before continuing.  

<div class=comp-code>

```python
import airflow
from airflow.operators.python_operator import BranchPythonOperator, PythonOperator
from airflow.operators.dummy_operator import DummyOperator
from airflow.models import DAG
import random

## setup the DAG w/ some sane defaults
args = {
    'owner': 'airflow',
    'start_date': airflow.utils.dates.days_ago(1)
}

dag = DAG(
    dag_id='example_dag_for_prefect',
    default_args=args,
    schedule_interval="@once")

## add a dummy task to run first
run_this_first = DummyOperator(task_id='run_this_first', dag=dag)

## add a conditional which will randomly choose to follow one of `branch_a` or `branch_b`
options = ['branch_a', 'branch_b']

branching = BranchPythonOperator(
    task_id='branching',
    python_callable=lambda: random.choice(options),
    dag=dag)

branching.set_upstream(run_this_first)

## add a dummy terminal task w/ a unique trigger
join = DummyOperator(
    task_id='join',
    trigger_rule='one_success',
    dag=dag
)


## will push an xcom with the value of "value"
def push_xcom(value, **kwargs):
    kwargs['ti'].xcom_push(key='value from push_xcom task', value=value)


for option in options:
    t = DummyOperator(task_id=option, dag=dag)
    t.set_upstream(branching)
    xcom_follow = PythonOperator(task_id='push_xcom_for_' + option, 
                                 dag=dag, 
                                 python_callable=lambda value=option, **kwargs: push_xcom(value, **kwargs),
                                 provide_context=True)
    t.set_downstream(xcom_follow)
    xcom_follow.set_downstream(join)
```
</div>

## Import DAG as a Prefect Flow
After adding the above DAG to your Airflow database, we can now import it as a Prefect flow and manipulate it as a first-class Prefect object.

::: tip Don't Panic
All code below is Prefect code!
:::

Let's begin by visualizing what our DAG looks like as Prefect flow.

```python
from prefect.utilities.airflow_utils import AirFlow


flow = AirFlow(dag_id='example_dag_for_prefect')
flow.visualize()
```

![](/airflow_dag.svg) {style="text-align: center;"}

Reminder: underlying each of these Prefect tasks is _still_ an Airflow task which is a part of an Airflow DAG; consequently, it is not currently recommended that you manipulate the individual tasks themselves.

However, we _can_ build on top of this using pure Prefect!  Importantly, because Prefect allows for dataflow as a first-class operation, we can add downstream dependencies of any task which pushes an XCom and use the pushed XCom value without touching Airflow!


```python
from prefect import task, triggers


@task(trigger=triggers.always_run, skip_on_upstream_skip=False) # discuss triggers and default skip cascading
def print_value(x):
    print(x)
    

xcom_a = flow.get_tasks(name='push_xcom_for_branch_a')[0]
xcom_b = flow.get_tasks(name='push_xcom_for_branch_b')[0]


with flow:
    # the value of the xcom that each push_xcom task created will be passed in as a function argument
    print_value(xcom_a) 
    print_value(xcom_b)
    
    
flow.visualize()
```

![svg](/extended_airflow_dag.svg) {style="text-align: center;"}

## Execution
In Airflow, time is intimately tied with DAG and task execution; that is not always the case in Prefect.  In order to execute a Prefect `AirFlow` (apologies for the pun) you will also need to provide an `execution_date` to the `run()` method - this is only necessary for flows which have been converted from Airflow.

When we execute this, we expect to see two print statements:
1. a print of the branch name which was run by the `branching` operator 
2. a print of `None` corresponding to the `print_value` task on the skipped branch


```python
from prefect.utilities.tests import raise_on_exception

flow_state = flow.run(execution_date='2018-09-20', return_tasks=flow.tasks)
#    branch_b
#    None
flow.visualize(flow_state=flow_state)
```

![svg](/run_airflow_dag.svg) {style="text-align: center;"}

This is just one way in which Prefect allows you to extend and _improve_ your Airflow DAGs!
