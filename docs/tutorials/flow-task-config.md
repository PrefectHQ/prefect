---
description: Explore the configuration available for Prefect flows and tasks.
tags:
    - tutorial
    - configuration
    - tasks
    - flows
    - parameters
    - caching
---

# Flow and task configuration

Now that you've written some basic flows and tasks, let's explore some of the configuration options that Prefect exposes.

In addition to the orchestration capabilities enabled by decorating functions as flows and tasks, you can also provide metadata used by Orion to execute and track your workflows.

## Basic flow configuration

Basic flow configuration includes the ability to provide a name, description, and version for the flow.

You specify flow configuration as options on the `@flow` decorator.

A flow `name` is a distinguished piece of metadata within Prefect. The name that you give to a flow becomes the unifying identifier for all future runs of that flow, regardless of version or task structure.

```python
@flow(name="My Example Flow")
def my_flow():
    # run tasks and subflows
```

A flow `description` enables you to provide documentation right alongside your flow object. You can also provide a specific `description` string as a flow option.

```python
@flow(name="My Example Flow", 
      description="An example flow for a tutorial.")
def my_flow():
    # run tasks and subflows
```

Prefect can also use the flow function's docstring as a description.

```python
@flow(name="My Example Flow")
    """An example flow for a tutorial."""
def my_flow():
    # run tasks and subflows
```

A flow `version` allows you to associate a given run of your workflow with the version of code or configuration that was used. 

```python
@flow(name="My Example Flow", 
      description="An example flow for a tutorial.",
      version="tutorial_02")
def my_flow():
    # run tasks and subflows
```

If you are using `git` to version control your code, you might use the commit hash as the version, as the following example shows. 

```python
@flow(name="My Example Flow", 
      description="An example flow for a tutorial.",
      version=os.getenv("GIT_COMMIT_SHA"))
def my_flow(*args, **kwargs):
    # run tasks and subflows
```

You don't have to supply a version for your flow. By default, Prefect makes a best effort to compute a stable hash of the `.py` file in which the flow is defined to automatically detect when your code changes.  However, this computation is not always possible and so, depending on your setup, you may see that your flow has a version of `None`.

### Parameter type conversion

Many of the available configuration options for Prefect flows also allow you to configure flow execution behavior.  One such option is the ability to perform type conversion for the parameters passed to your flow function.  This is most easily demonstrated via a simple example:

```python
from prefect import task, flow

@task
def printer(obj):
    print(f"Received a {type(obj)} with value {obj}")

# note that we define the flow with type hints
@flow
def validation_flow(x: int, y: str):
    printer(x)
    printer(y)
```

Let's now run this flow, but provide values that don't perfectly conform to the type hints provided:

<div class="termy">
```
>>> validation_flow(x="42", y=100)
Received a &#60;class 'int'&#62; with value 42
Received a &#60;class 'str'&#62; with value 100
```
</div>

You can see that Prefect coerced the provided inputs into the types specified on your flow function!  

While the above example is basic, this can be extended in powerful ways. In particular, _any_ [pydantic](https://pydantic-docs.helpmanual.io/) model type hint will be coerced into the correct form automatically:

```python
from prefect import flow
from pydantic import BaseModel

class Model(BaseModel):
    a: int
    b: float
    c: str

@flow
def model_validator(model: Model):
    printer(model)
```

<div class="termy">
```
>>> model_validator({"a": 42, "b": 0, "c": 55})
Received a &#60;class '__main__.Model'&#62; with value a=42 b=0.0 c='55'
```
</div>

!!! note "This behavior can be toggled"
    If you would like to turn this feature off for any reason, you can provide `validate_parameters=False` to your flow decorator and Prefect will passively accept whatever input values you provide.

    For more information, please refer to the [pydantic documentation](https://pydantic-docs.helpmanual.io/usage/models/).

### Configuring task runners

A more advanced configuration option for flows is `task_runner`, which enables you to specify the execution environment used for task runs within a flow. We'll cover the use cases for task runners in a future tutorial. 

For now, we'll just demonstrate that you can specify the task runner _almost_ like any other option: the difference is that you need to import the task runner first, then specify you're using it with the `task_runner` option:

```python
from prefect.task_runners import DaskTaskRunner

@flow(name="My Example Flow", 
      task_runner=DaskTaskRunner())
def my_flow(*args, **kwargs):
    # run parallel tasks and subflows with Dask
```

Some task runners, such as the `DaskTaskRunner` and `RayTaskRunner`, can take additional, optional configuration of their own. See the [task runners tutorials](/tutorials/dask-task-runner/) and [Task Runners](/concepts/task-runners/) documentation for details.

## Basic task configuration

By design, tasks follow a very similar metadata model to flows: you can independently assign tasks their own name and description.

```python
@task(name="My Example Task", 
      description="An example task for a tutorial.")
def my_task():
    # do some work
```

Tasks also accept [tags](/concepts/tasks/#tags) as an option. When you begin using Prefect Orion's orchestration features and UI, tags become a powerful tool for filtering and managing not just tasks, but flows and deployments as well.

```python
@task(name="My Example Task", 
      description="An example task for a tutorial.",
      tags=["tutorial","tag-test"])
def my_task():
    # do some work
```

### Task retries

Prefect allows for off-the-shelf configuration of task-level retries.  The only two decisions you need to make are how many retries you want to attempt and what delay you need between run attempts:

```python
from prefect import task, flow

@task(retries=2, retry_delay_seconds=0)
def failure():
    print('running')
    raise ValueError("bad code")

@flow
def test_retries():
    return failure()
```

If you run `test_retries()`, the `failure()` task always raises an error, but will run a total of three times.

<div class="termy">
```
>>> state = test_retries()
13:48:40.570 | Beginning flow run 'red-orca' for flow 'test-retries'...
13:48:40.570 | Starting task runner `SequentialTaskRunner`...
13:48:40.630 | Submitting task run 'failure-acc38180-0' to task runner...
running
13:48:40.663 | Task run 'failure-acc38180-0' encountered exception:
Traceback (most recent call last):...
13:48:40.708 | Task run 'failure-acc38180-0' received non-final state 
'AwaitingRetry' when proposing final state 'Failed' and will attempt to run again...
running
13:48:40.748 | Task run 'failure-acc38180-0' encountered exception:
Traceback (most recent call last):...
13:48:40.786 | Task run 'failure-acc38180-0' received non-final state 
'AwaitingRetry' when proposing final state 'Failed' and will attempt to run again...
running
13:48:40.829 | Task run 'failure-acc38180-0' encountered exception:
Traceback (most recent call last):...
13:48:40.871 | Task run 'failure-acc38180-0' finished in state 
Failed(message='Task run encountered an exception.', type=FAILED)
13:48:40.872 | Shutting down task runner `SequentialTaskRunner`...
13:48:40.899 | Flow run 'red-orca' finished in state 
Failed(message='1/1 states failed.', type=FAILED)
```
</div>

Once we dive deeper into state transitions and orchestration policies, you will see that this task run actually went through the following state transitions some number of times: 

`Pending` -> `Running` -> `AwaitingRetry` -> `Retrying` 

Metadata such as this allows for a full reconstruction of what happened with your flows and tasks on each run.

### Task caching

Caching refers to the ability of a task run to reflect a finished state without actually running the code that defines the task. This allows you to efficiently reuse results of tasks that may be particularly "expensive" to run with every flow run.  Moreover, Prefect makes it easy to share these states across flows and flow runs using the concept of a "cache key".  

To illustrate, run the following flow in a REPL:

```python
from prefect import task, flow

def static_cache_key(context, parameters):
    # return a constant
    return "static cache key"

@task(cache_key_fn=static_cache_key)
def cached_task():
    print('running an expensive operation')
    return 42

@task
def printer(val):
    print(val)

@flow
def test_caching():
    cached_task()
    cached_task()

@flow
def another_flow():
    printer(cached_task())
```

<div class="termy">
```
>>> test_caching()
21:22:36.487 | INFO    | prefect.engine - Created flow run 'dainty-jaguarundi' for flow 'test-caching'
21:22:36.488 | INFO    | Flow run 'dainty-jaguarundi' - Using task runner 'ConcurrentTaskRunner'
21:22:36.546 | INFO    | Flow run 'dainty-jaguarundi' - Created task run 'cached_task-64beb460-0' for task 'cached_task'
21:22:36.603 | INFO    | Flow run 'dainty-jaguarundi' - Created task run 'cached_task-64beb460-1' for task 'cached_task'
running an expensive operation
running an expensive operation
21:22:36.715 | INFO    | Task run 'cached_task-64beb460-0' - Finished in state Completed(None)
21:22:36.730 | INFO    | Task run 'cached_task-64beb460-1' - Finished in state Completed(None)
21:22:37.175 | INFO    | Flow run 'dainty-jaguarundi' - Finished in state Completed('All states completed.')
>>> another_flow()
21:22:50.635 | INFO    | prefect.engine - Created flow run 'macho-coucal' for flow 'another-flow'
21:22:50.635 | INFO    | Flow run 'macho-coucal' - Using task runner 'ConcurrentTaskRunner'
21:22:50.693 | INFO    | Flow run 'macho-coucal' - Created task run 'cached_task-64beb460-2' for task 'cached_task'
21:22:50.742 | INFO    | Flow run 'macho-coucal' - Created task run 'printer-da44fb11-0' for task 'printer'
21:22:50.786 | INFO    | Task run 'cached_task-64beb460-2' - Finished in state Cached(None, type=COMPLETED)
42
21:22:51.048 | INFO    | Task run 'printer-da44fb11-0' - Finished in state Completed(None)
21:22:51.435 | INFO    | Flow run 'macho-coucal' - Finished in state Completed('All states completed.')
```
</div>

Notice that the `cached_task` only ran one time across both flow runs!  Whenever each task run requested to enter a `Running` state, it provided its cache key computed from the `cache_key_fn`.  The Orion server identified that there was a `COMPLETED` state associated with this key and instructed the run to immediately enter the same state, including the same return values. See the Tasks [Caching](/concepts/tasks/#caching) documentation for more details.

!!! warning "The persistence of state"
    Note that up until now we have run all of our workflows interactively. This means that our metadata store is a SQLite database located at the default database location: `~/.prefect/orion.db`.  This can be configured in various ways, but please note that any cache keys you experiment with will be persisted in this SQLite database until you clear it manually!

!!! tip "Additional Reading"
    To learn more about the concepts presented here, check out the following resources:

    - [Flows](/concepts/flows/)
    - [Tasks](/concepts/tasks/)
    - [States](/concepts/states/)
