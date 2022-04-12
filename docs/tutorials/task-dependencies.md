---
description: Learn about controlling data and execution dependencies between Prefect tasks.
tags:
    - tasks
    - error handling
    - dependencies
    - task order
    - data dependencies
    - state
---

# Task dependencies

One of the core features of Prefect is the ability to control dependencies between tasks. This includes tasks that exchange data and those that need to execute in a pre-specified order due to external side effects.

## A working example

To set the stage, let's start with the following Python script that creates some SQLite3 tables and adds data to them:

```python
import datetime
import json
import sqlite3
import sys

def create_tables(connection):
    sql_create_projects_table = """CREATE TABLE IF NOT EXISTS projects (
                                        id integer PRIMARY KEY,
                                        name text NOT NULL,
                                        begin_date text
                                        CHECK(length("name") >= 4)
                                    ); """

    cur = connection.cursor()
    cur.execute(sql_create_projects_table)
    connection.commit()

def add_project(connection, name):
    sql = '''INSERT INTO projects(name,begin_date)
              VALUES(?,?) '''
    cur = connection.cursor()
    cur.execute(sql, (name, str(datetime.datetime.utcnow())))
    connection.commit()
    return cur.lastrowid

def main(project_names, db_file="/tmp/example.db"):
    connection = sqlite3.connect(db_file) 
    create_tables(connection) 

    for name in project_names:
        add_project(connection, name)

if __name__ == "__main__":
    main(json.loads(sys.argv[1]))
```

We can save this script as `example.py` and confirm it worked from the command line:

<div class="termy">
```
$ python example.py '["prefect"]'
$ sqlite3 /tmp/example.db 
SQLite version 3.33.0 2020-08-14 13:23:32
Enter ".help" for usage hints.
$ .tables
projects
$ SELECT * FROM projects;
1|prefect|2021-09-30 17:04:46.701471
```
</div>

## Error handling

Suppose that one day some bad data gets into our CLI call:

<div class="termy">
```
$ python example.py '["orion", "", "critically-important"]' 
sqlite3.IntegrityError: CHECK constraint failed: projects
```
</div>

Depending on how we have instrumented this script, it may be a while before we realize that the "critically-important" project was not correctly added to our database due to bad data!  

Prefect helps remove this edge case from your workflows by managing your tasks' state automatically.  We can quickly convert the above example to a state managed Prefect flow:

```python
from prefect import task, flow

@task
def create_tables(connection):
    ...

@task
def add_project(connection, name):
    ...

@flow(name="Add Projects to DB")
def main(project_names, db_file="/tmp/example.db"):

    # prefect may switch threads 
    connection = sqlite3.connect(db_file, check_same_thread=False) 
    create_tables(connection) 

    for name in project_names:
        add_project(connection, name)
```

When we run this as a flow, the "critically-important" project is indeed created! 

<div class="termy">
```
$ python example.py '["orion", "", "critically-important"]'
14:52:47.292 | Beginning flow run 'neon-guan' for flow 'Add Projects to DB'...
14:52:47.292 | Starting task runner `SequentialTaskRunner`...
14:52:47.373 | Submitting task run 'create_tables-45cf78d2-0' to task runner...
14:52:47.490 | Task run 'create_tables-45cf78d2-0' finished in state 
Completed(message=None, type=COMPLETED)
14:52:47.527 | Submitting task run 'add_project-80de7cb5-0' to task runner...
14:52:47.599 | Task run 'add_project-80de7cb5-0' finished in state 
Completed(message=None, type=COMPLETED)
14:52:47.634 | Submitting task run 'add_project-80de7cb5-1' to task runner...
14:52:47.664 | Task run 'add_project-80de7cb5-1' encountered exception:
Traceback (most recent call last):...
sqlite3.IntegrityError: CHECK constraint failed: projects
14:52:47.702 | Task run 'add_project-80de7cb5-1' finished in state 
Failed(message='Task run encountered an exception.', type=FAILED)
14:52:47.737 | Submitting task run 'add_project-80de7cb5-2' to task runner...
14:52:47.808 | Task run 'add_project-80de7cb5-2' finished in state 
Completed(message=None, type=COMPLETED)
14:52:47.810 | Shutting down task runner `SequentialTaskRunner`...
14:52:47.838 | Flow run 'neon-guan' finished in state 
Failed(message='1/4 states failed.', type=FAILED)
```
</div>

Note that the final state of the flow run is failed, as we would expect given that one of the tasks did fail due to the integrity check.

## Enforcing State Dependencies

You may have observed that all of the `add_project` tasks have an implicit dependency on `create_tables` finishing successfully &mdash; if the table isn't created, then we have no need to run these tasks as we know they will fail.  In more complex use cases, they may actually "succeed", but not produce the correct effect if this dependency is not enforced!

Luckily, Prefect makes it easy to configure a state dependency between two or more task runs using the special `wait_for` keyword argument:

```python
@flow(name="Add Projects to DB")
def main(project_names, db_file="/tmp/example.db"):

    # prefect may switch threads 
    connection = sqlite3.connect(db_file, check_same_thread=False) 
    table_task = create_tables(connection) 

    for name in project_names:
        add_project(connection, name, wait_for=[table_task])
```

If for any reason the creation of the table fails, you will find that the `add_project` task runs are left in a PENDING 'NotReady' state.

!!! tip "Inspecting state programmatically"
    To inspect your flow and task run states programmatically, you can use the `result()` method available on all Prefect state objects:

    ```python
    flow_state = main(["test", "other"])
    # returns a list of task run states
    task_run_states = flow_state.result(raise_on_failure=False) 
    ```

    Note the use of `raise_on_failure=False`. The default behavior of this method is to re-raise any caught exceptions for traceback inspection.

## Advanced: Manual manipulation of state

While Prefect takes care of all state handling automatically, there are some situations in which you may want to inspect task run state at runtime. For example, you may want to implement custom dynamic logic that depends on whether a task succeeded or failed, or the return value of a task.

Achieving this requires an understanding of the return value of a task run, which is a `PrefectFuture`.  Prefect futures are asynchronous representations of the task run that allow for state inspection possibly even before a task run is complete.

The two relevant methods for futures are:

- `wait`: when called, blocks until the underlying task run is complete and returns its final state.
- `get_state`: immediately query for the current state of the underlying task run and return it.

Using the `DaskTaskRunner` we can see this clearly:

```python
import random
import time

from prefect import task, flow
from prefect.task_runners import DaskTaskRunner

@task
def sleep(secs):
    print('Beginning to sleep...')
    time.sleep(secs)
    return random.random()

@task
def fail():
    raise TypeError("Something was misconfigured")

@flow(task_runner=DaskTaskRunner())
def complex_flow_logic():
    long_sleep = sleep(10)

    time.sleep(2)
    if long_sleep.get_state().is_running():
        # can run custom code here!
        # including conditionally running other tasks
        print('Long sleep task is still running!')

    # blocks until complete and returns state
    state = long_sleep.wait() 
    if state.result() > 0.5:
        # conditionally run another task based on the output
        print('running fail task')
        fail()
    else:
        print('result was good')
```

!!! warning "`result()` may raise an exception"
    Be aware that calling `state.result()` may raise an exception if the underlying task fails. This will have the affect of aborting your flow run.  To avoid this behavior, pass `raise_on_failure=False` to the result method.

As we can see here, mixing native Python logic with your Prefect tasks is straightforward once you understand the behavior of Prefect futures and states!

!!! tip "Additional Reading"
    To learn more about the concepts presented here, check out the following resources:

    - [Tasks](/concepts/tasks/)
    - [States](/concepts/states/)
