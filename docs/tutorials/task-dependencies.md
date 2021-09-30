# Task dependencies

One of the core features of Prefect is the ability to control dependencies between tasks - this incldues tasks that exchange data and those that need to execute in a pre-specified order due to external side effects.  


## A working example

To set the stage, let's start with the following Python script that creates some sqlite3 tables and adds data to them:

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


def main(project_names, db_file="example.db"):
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
$ sqlite3 example.db 
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
def main(project_names, db_file="example.db")

    # prefect may switch threads 
    connection = sqlite3.connect(db_file, check_same_thread=False) 
    create_tables(connection) 

    for name in project_names:
        add_project(connection, name)
```

And find that when we run this as a flow (which can still be achieved with our CLI setup!) the "criticaly-important" project is indeed created!  
```python
>>> main(["orion", "", "critically-important"])
State(name='Failed', type=StateType.FAILED, message='1/4 states failed.')
```

Note that the final state of the flow run is failed, as we would expect given that one of the tasks did fail due to the integrity check.

## Enforcing State Dependencies

You may have observed that all of the `add_project` tasks have an implicit depedency on `create_tables` finishing successfully - if the table isn't created, then we have no need to run these tasks as we know they will fail.  In more complex use cases, they may actually "succeed" but not produce the correct effect if this dependency is not enforced!

Luckily, Prefect makes it easy to configure a state dependency between two or more task runs using the special `wait_for` keyword argument:
```python
@flow(name="Add Projects to DB")
def main(project_names, db_file="example.db")

    # prefect may switch threads 
    connection = sqlite3.connect(db_file, check_same_thread=False) 
    table_task = create_tables(connection) 

    for name in project_names:
        add_project(connection, name, wait_for=[table_task])
```

- custom management of state
- extracting data from a task (not a prefect dependency!)

While including all of your logic within Prefect tasks offers many benefits, there are situations in which you may want to interact with your task's state and return values using native Python.
