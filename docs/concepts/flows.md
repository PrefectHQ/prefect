---
description: Prefect flows are the foundational containers for workflow logic
tags:
    - Orion
    - flows
    - subflows
    - parameters
    - states
---

# Flows

Flows are the most basic Prefect object. Flows are the only Prefect abstraction that can be interacted with, displayed, and run without needing to reference any other aspect of the Prefect engine. A flow is a container for workflow logic and allows users to interact with and reason about the state of their workflows. It is represented in Python as a single function.

## Flows overview

Flows are like functions. They can take inputs, perform work, and return an output. In fact, you can turn any function into a Prefect flow by adding the `@flow` decorator. When a function becomes a flow, its behavior changes, giving it advantages.

Flows also take advantage of automatic Prefect logging to capture details about flow runs such as runtime, tags, and final state. Flows are required for [deployments](/concepts/deployments/) &mdash; every deployment points to a specific flow as the entrypoint of an API-generated flow run.

All workflows are defined within the context of a flow. Flows can include calls to [tasks](/concepts/tasks/) as well as to other flows, which we call ["subflows"](#subflows) in this context. Flows may be defined within modules and imported for use as subflows in your flow definitions. 

!!! warning Tasks must be called from flows
    All tasks must be called from within a flow. Tasks may not be called from other tasks.

For most use cases, we recommend using the [`@flow`][prefect.flows.flow] decorator to designate a flow:

```python hl_lines="3"
from prefect import flow

@flow
def my_flow():
    return
```

Flows are uniquely identified by name. You can provide a `name` parameter value for the flow. If you don't provide a name, Prefect uses the flow function name. 

```python hl_lines="1"
@flow(name="My Flow")
def my_flow():
    return
```

Flows can call tasks to do specific work:

```python
from prefect import flow, task

@task
def print_hello(name):
    print(f"Hello {name}!")

@flow(name="Hello Flow")
def hello_world(name="world"):
    print_hello(name)
```

!!! tip Flows and tasks
    There's nothing stopping you from putting all of your code in a single flow function &mdash; Prefect will happily run it! 
    
    However, organizing your workflow code into smaller flow and task units lets you take advantage of Prefect features like retries, more granular visibility into runtime state, the ability to determine final state regardless of individual task state, and more.
    
    In addition, if you put all of your workflow logic in a single flow function and any line of code fails, the entire flow will fail and must be retried from the beginning. This can be avoided by breaking up the code into multiple tasks.

    Each Prefect workflow must contain one primary `@flow` function. From that flow function, you may call any number of other tasks, subflows, and even regular Python functions. You can pass parameters to your primary flow function that will be used elsewhere in the workflow, and the [final state](#final-state-determination) of that primary flow function determines the final state of your workflow.

    Prefect encourages "small tasks" &mdash; each one should represent a single logical step of your workflow. This allows Prefect to better contain task failures.

## Flow arguments

Flows allow a great deal of configuration via arguments. Flows accept the following optional arguments.

| Argument | Description |
| --- | --- |
| name | An optional name for the flow. If not provided, the name will be inferred from the function. | 
| version | An optional version string for the flow. If not provided, we will attempt to create a version string as a hash of the file containing the wrapped function. If the file cannot be located, the version will be null. | 
| task_runner | The [task runner](/concepts/task-runners/) to use for task execution within the flow. If not provided, the `ConcurrentTaskRunner` will be used. | 
| description | An optional string description for the flow. If not provided, the description will be pulled from the docstring for the decorated function. | 
| timeout_seconds | An optional number of seconds indicating a maximum runtime for the flow. If the flow exceeds this runtime, it will be marked as failed. Flow execution may continue until the next task is called. | 
| validate_parameters | Boolean indicating whether parameters passed to flows are validated by Pydantic. Default is `True`.  | 

For example, you can provide a `name` value for the flow. Here we've also used the optional `description` argument and specified a non-default task runner.

```python
from prefect import flow
from prefect.task_runners import SequentialTaskRunner

@flow(name="My Flow",
      description="My flow using SequentialTaskRunner",
      task_runner=SequentialTaskRunner())
def my_flow():
    return
```

Note that `validate_parameters` will check that input values conform to the annotated types on the function. Where possible, values will be coerced into the correct type. For example, if a parameter is defined as `x: int` and "5" is passed, it will be resolved to `5`. If set to `False`, no validation will be performed on flow parameters.

## Composing flows

The simplest workflow is just a `@flow` function that does all the work of the workflow. 

```python
from prefect import flow

@flow(name="Hello Flow")
def hello_world(name="world"):
    print(f"Hello {name}!")

hello_world("Marvin")
```

When you run this flow, you'll see the following output:

<div class="terminal">
```bash
$ python hello.py
15:11:23.594 | INFO    | prefect.engine - Created flow run 'benevolent-donkey' for flow 'hello-world'
15:11:23.594 | INFO    | Flow run 'benevolent-donkey' - Using task runner 'ConcurrentTaskRunner'
Hello Marvin!
15:11:24.447 | INFO    | Flow run 'benevolent-donkey' - Finished in state Completed()
```
</div>

A better practice is to create `@task` functions that do the specific work of your flow, and use your `@flow` function as the conductor that orchestrates the flow of your application:

```python
from prefect import flow, task

@task(name="Print Hello")
def print_hello(name):
    msg = f"Hello {name}!"
    print(msg)
    return msg

@flow(name="Hello Flow")
def hello_world(name="world"):
    message = print_hello(name)

hello_world("Marvin")
```

When you run this flow, you'll see the following output, which illustrates how the work is encapsulated in a task run.

<div class="terminal">
```bash
$ python hello.py
15:15:58.673 | INFO    | prefect.engine - Created flow run 'loose-wolverine' for flow 'Hello Flow'
15:15:58.674 | INFO    | Flow run 'loose-wolverine' - Using task runner 'ConcurrentTaskRunner'
15:15:58.973 | INFO    | Flow run 'loose-wolverine' - Created task run 'Print Hello-84f0fe0e-0' for task 'Print Hello'
Hello Marvin!
15:15:59.037 | INFO    | Task run 'Print Hello-84f0fe0e-0' - Finished in state Completed()
15:15:59.568 | INFO    | Flow run 'loose-wolverine' - Finished in state Completed('All states completed.')
```
</div>

## Subflows

A _subflow_ run is created when a flow function is called inside the execution of another flow. The primary flow is the "parent" flow. The flow created within the parent is the "child" flow or "subflow."

Subflow runs behave like normal flow runs. There is a full representation of the flow run in the backend as if it had been called separately. When a subflow starts, it will create a new [task runner](/concepts/task-runners/) and tasks within the subflow are submitted to it. When the subflow completes, the task runner is shut down.

Unlike tasks, subflows will block until completion with all task runners. However, asynchronous subflows can be run in parallel by using [AnyIO task groups](https://anyio.readthedocs.io/en/stable/tasks.html) or [asyncio.gather](https://docs.python.org/3/library/asyncio-task.html#id6).

Subflows differ from normal flows in that they will resolve any passed task futures into data. This allows data to be passed from the parent flow to the child easily.

The relationship between a child and parent flow is tracked by creating a special task run in the the parent flow. This task run will mirror the state of the child flow run.

A task that represents a subflow will be annotated as such in its `state_details` via the presence of a `child_flow_run_id` field.  A subflow can be identified via the presence of a `parent_task_run_id` on `state_details`.

You can define multiple flows within the same file. Whether running locally or via a [deployment](/concepts/deployments/), you must indicate which flow is the entrypoint for a flow run.

```python
from prefect import flow, task

@task(name="Print Hello")
def print_hello(name):
    msg = f"Hello {name}!"
    print(msg)
    return msg

@flow(name="Subflow")
def my_subflow(msg):
    print(f"Subflow says: {msg}")

@flow(name="Hello Flow")
def hello_world(name="world"):
    message = print_hello(name)
    my_subflow(message)

hello_world("Marvin")
```

You can also define flows or tasks as separate modules and import them into a flow definition. For example, here's a simple subflow module:

```python
from prefect import flow, task

@flow(name="Subflow")
def my_subflow(msg):
    print(f"Subflow says: {msg}")
```

Here's a parent flow that imports and uses `my_subflow()` as a subflow:

```python
from prefect import flow, task
from subflow import my_subflow

@task(name="Print Hello")
def print_hello(name):
    msg = f"Hello {name}!"
    print(msg)
    return msg

@flow(name="Hello Flow")
def hello_world(name="world"):
    message = print_hello(name)
    my_subflow(message)

hello_world("Marvin")
```

Running the `hello_world()` flow (in this example from the file `hello.py`) creates a flow run like this:

<div class="terminal">
```bash
$ python hello.py
15:19:21.651 | INFO    | prefect.engine - Created flow run 'daft-cougar' for flow 'Hello Flow'
15:19:21.651 | INFO    | Flow run 'daft-cougar' - Using task runner 'ConcurrentTaskRunner'
15:19:21.945 | INFO    | Flow run 'daft-cougar' - Created task run 'Print Hello-84f0fe0e-0' for task 'Print Hello'
Hello Marvin!
15:19:22.055 | INFO    | Task run 'Print Hello-84f0fe0e-0' - Finished in state Completed()
15:19:22.107 | INFO    | Flow run 'daft-cougar' - Created subflow run 'ninja-duck' for flow 'Subflow'
Subflow says: Hello Marvin!
15:19:22.794 | INFO    | Flow run 'ninja-duck' - Finished in state Completed()
15:19:23.215 | INFO    | Flow run 'daft-cougar' - Finished in state Completed('All states completed.')
```
</div>

## Parameters

Flows can be called with both positional and keyword arguments. These arguments are resolved at runtime into a dictionary of **parameters** mapping name to value. These parameters are stored by the Prefect Orion orchestration engine on the flow run object. 

!!! warning Prefect API requires keyword arguments
    When creating flow runs from the Prefect Orion API, parameter names must be specified when overriding defaults &mdash; they cannot be positional.

Type hints provide an easy way to enforce typing on your flow parameters via [pydantic](https://pydantic-docs.helpmanual.io/).  This means _any_ pydantic model used as a type hint within a flow will be coerced automatically into the relevant object type:

```python
from prefect import flow
from pydantic import BaseModel

class Model(BaseModel):
    a: int
    b: float
    c: str

@flow
def model_validator(model: Model):
    print(model)
```

Note that parameter values can be provided to a flow via API using the concept of a [deployment](/concepts/deployments/). Flow run parameters sent to the API on flow calls are coerced to a serializable form. Type hints on your flow functions provide you a way of automatically coercing JSON provided values to their appropriate Python representation.  

For example, to automatically convert something to a datetime:

```python
from prefect import flow
from datetime import datetime

@flow
def what_day_is_it(date: datetime = None):
    if date is None:
        date = datetime.utcnow()
    print(f"It was {date.strftime('%A')} on {date.isoformat()}")

what_day_is_it("2021-01-01T02:00:19.180906")
# It was Friday on 2021-01-01T02:00:19.180906
```

Parameters are validated before a flow is run. If a flow call receives invalid parameters, a flow run is created in a `Failed` state. If a flow run for a deployment receives invalid parameters, it will move from a `Pending` state to a `Failed` without entering a `Running` state.

## Tags

Coming soon.

## Final state determination

The final state of the flow is determined by its return value.  The following rules apply:

- If an exception is raised directly in the flow function, the flow run is marked as failed.
- If the flow does not return a value (or returns `None`), its state is determined by the states of all of the tasks and subflows within it. In particular, if _any_ task run or subflow run failed, then the final flow run state is marked as failed.
- If a flow returns one or more [task run futures](/api-ref/prefect/futures/#prefect.futures.PrefectFuture) or states, these runs are used as the _reference tasks_ for determining the final state of the run. If _any_ of the returned task runs fail, the flow run is marked as failed.
- If a flow returns a manually created state, it is used as the state of the final flow run. This allows for manual determination of final state.
- If the flow run returns _any other object_, then it is marked as successfully completed.

The following examples illustrate each of these cases:

### Raise an exception

If an exception is raised within the flow function, the flow is immediately marked as failed.

```python hl_lines="5"
from prefect import flow

@flow
def always_fail_flow():
    raise ValueError("This flow immediately fails")
```

Running this flow produces the following result:

<div class="terminal">
```bash
20:49:07.776 | INFO    | prefect.engine - Created flow run 'mustard-shrimp' for flow 'always-fail-flow'
20:49:07.776 | INFO    | Flow run 'mustard-shrimp' - Using task runner 'ConcurrentTaskRunner'
20:49:08.046 | ERROR   | Flow run 'mustard-shrimp' - Encountered exception during execution:
Traceback (most recent call last):...
ValueError: This flow immediately fails
20:49:08.683 | ERROR   | Flow run 'mustard-shrimp' - Finished in state Failed('Flow run encountered an exception.')
Failed(message='Flow run encountered an exception.', type=FAILED, result=ValueError('This flow immediately fails'), flow_run_id=c1a4af77-e273-4a5b-8676-bfe1852f4612)
```
</div>

### Return None

A flow with no return statement is determined by the state of all of its task runs.

```python
from prefect import flow, task

@task
def always_fails_task():
    raise ValueError("I am bad task")

@task
def always_succeeds_task():
    return "foo"

@flow
def always_fails_flow():
    always_fails_task()
    always_succeeds_task()
```

Running this flow produces the following result:

<div class="terminal">
```bash
20:52:06.982 | INFO    | prefect.engine - Created flow run 'affable-monkey' for flow 'always-fails-flow'
20:52:06.983 | INFO    | Flow run 'affable-monkey' - Using task runner 'ConcurrentTaskRunner'
20:52:07.087 | INFO    | Flow run 'affable-monkey' - Created task run 'always_fails_task-58ea43a6-0' for task 'always_fails_task'
20:52:07.131 | INFO    | Flow run 'affable-monkey' - Created task run 'always_succeeds_task-c9014725-0' for task 'always_succeeds_task'
20:52:07.154 | ERROR   | Task run 'always_fails_task-58ea43a6-0' - Encountered exception during execution:
Traceback (most recent call last):...
ValueError: I am bad task
20:52:07.192 | ERROR   | Task run 'always_fails_task-58ea43a6-0' - Finished in state Failed('Task run encountered an exception.')
20:52:07.205 | INFO    | Task run 'always_succeeds_task-c9014725-0' - Finished in state Completed()
20:52:07.782 | ERROR   | Flow run 'affable-monkey' - Finished in state Failed('1/2 states failed.')
Failed(message='1/2 states failed.', type=FAILED, result=[Failed(message='Task run encountered an exception.', type=FAILED, result=ValueError('I am bad task'), task_run_id=52b562be-c605-4688-941b-26409ba43700), Completed(message=None, type=COMPLETED, result='foo', task_run_id=cc0b6837-e9fc-4231-9de6-3557d74d9f0d)], flow_run_id=786549ae-2ad1-409f-bfde-64a3e0e0b823)
```
</div>

### Return a future

If a flow returns one or more futures, the final state is determined based on the underlying states.

```python hl_lines="15"
from prefect import task, flow

@task
def always_fails_task():
    raise ValueError("I am bad task")

@task
def always_succeeds_task():
    return "foo"

@flow
def always_succeeds_flow():
    x = always_fails_task()
    y = always_succeeds_task()
    return y
```

Running this flow produces the following result &mdash; it succeeds because it returns the future of the task that succeeds:

<div class="terminal">
```bash
20:55:29.886 | INFO    | prefect.engine - Created flow run 'obedient-pheasant' for flow 'always-succeeds-flow'
20:55:29.886 | INFO    | Flow run 'obedient-pheasant' - Using task runner 'ConcurrentTaskRunner'
20:55:29.981 | INFO    | Flow run 'obedient-pheasant' - Created task run 'always_fails_task-58ea43a6-0' for task 'always_fails_task'
20:55:30.020 | INFO    | Flow run 'obedient-pheasant' - Created task run 'always_succeeds_task-c9014725-0' for task 'always_succeeds_task'
20:55:30.043 | ERROR   | Task run 'always_fails_task-58ea43a6-0' - Encountered exception during execution:
Traceback (most recent call last):...
ValueError: I am bad task
20:55:30.098 | ERROR   | Task run 'always_fails_task-58ea43a6-0' - Finished in state Failed('Task run encountered an exception.')
20:55:30.117 | INFO    | Task run 'always_succeeds_task-c9014725-0' - Finished in state Completed()
20:55:30.726 | INFO    | Flow run 'obedient-pheasant' - Finished in state Completed('All states completed.')
Completed(message='All states completed.', type=COMPLETED, result=Completed(message=None, type=COMPLETED, result='foo', task_run_id=b48cbd0d-ebf0-460b-88bd-5bc18202d368), flow_run_id=42f8251e-2e13-4bbb-a70d-55275a2e2f5e)
```
</div>

### Return multiple states or futures

If a flow returns a mix of futures and states, the final state is determined by resolving all futures to states, then determining if any of the states are not `COMPLETED`.

```python hl_lines="20"
from prefect import task, flow

@task
def always_fails_task():
    raise ValueError("I am bad task")

@task
def always_succeeds_task():
    return "foo"

@flow
def always_succeeds_flow():
    return "bar"

@flow
def always_fails_flow():
    x = always_fails_task()
    y = always_succeeds_task()
    z = always_succeeds_flow()
    return x, y, z
```

Running this flow produces the following result. It fails because one of the three returned futures failed. Note that the final state is `Failed`, but the states of each of the returned futures is included in the flow state:

<div class="terminal">
```bash
20:57:51.547 | INFO    | prefect.engine - Created flow run 'impartial-gorilla' for flow 'always-fails-flow'
20:57:51.548 | INFO    | Flow run 'impartial-gorilla' - Using task runner 'ConcurrentTaskRunner'
20:57:51.645 | INFO    | Flow run 'impartial-gorilla' - Created task run 'always_fails_task-58ea43a6-0' for task 'always_fails_task'
20:57:51.686 | INFO    | Flow run 'impartial-gorilla' - Created task run 'always_succeeds_task-c9014725-0' for task 'always_succeeds_task'
20:57:51.727 | ERROR   | Task run 'always_fails_task-58ea43a6-0' - Encountered exception during execution:
Traceback (most recent call last):...
ValueError: I am bad task
20:57:51.787 | INFO    | Task run 'always_succeeds_task-c9014725-0' - Finished in state Completed()
20:57:51.808 | INFO    | Flow run 'impartial-gorilla' - Created subflow run 'unbiased-firefly' for flow 'always-succeeds-flow'
20:57:51.884 | ERROR   | Task run 'always_fails_task-58ea43a6-0' - Finished in state Failed('Task run encountered an exception.')
20:57:52.438 | INFO    | Flow run 'unbiased-firefly' - Finished in state Completed()
20:57:52.811 | ERROR   | Flow run 'impartial-gorilla' - Finished in state Failed('1/3 states failed.')
Failed(message='1/3 states failed.', type=FAILED, result=(Failed(message='Task run encountered an exception.', type=FAILED, result=ValueError('I am bad task'), task_run_id=5fd4c697-7c4c-440d-8ebc-dd9c5bbf2245), Completed(message=None, type=COMPLETED, result='foo', task_run_id=df9b6256-f8ac-457c-ba69-0638ac9b9367), Completed(message=None, type=COMPLETED, result='bar', task_run_id=cfdbf4f1-dccd-4816-8d0f-128750017d0c)), flow_run_id=6d2ec094-001a-4cb0-a24e-d2051db6318d)
```
</div>

### Return a manual state

If a flow returns a manually created state, the final state is determined based on the return value.

```python hl_lines="16-19"
from prefect import task, flow
from prefect.orion.schemas.states import Completed, Failed

@task
def always_fails_task():
    raise ValueError("I am bad task")

@task
def always_succeeds_task():
    return "foo"

@flow
def always_succeeds_flow():
    x = always_fails_task()
    y = always_succeeds_task()
    if y.result() == "foo":
        return Completed(message="I am happy with this result")
    else:
        return Failed(message="How did this happen!?")
```

Running this flow produces the following result.

<div class="terminal">
```bash
21:01:25.332 | INFO    | prefect.engine - Created flow run 'vivid-chachalaca' for flow 'always-succeeds-flow'
21:01:25.332 | INFO    | Flow run 'vivid-chachalaca' - Using task runner 'ConcurrentTaskRunner'
21:01:25.436 | INFO    | Flow run 'vivid-chachalaca' - Created task run 'always_fails_task-58ea43a6-0' for task 'always_fails_task'
21:01:25.477 | INFO    | Flow run 'vivid-chachalaca' - Created task run 'always_succeeds_task-c9014725-0' for task 'always_succeeds_task'
21:01:25.503 | ERROR   | Task run 'always_fails_task-58ea43a6-0' - Encountered exception during execution:
Traceback (most recent call last):...
ValueError: I am bad task
21:01:25.539 | ERROR   | Task run 'always_fails_task-58ea43a6-0' - Finished in state Failed('Task run encountered an exception.')
21:01:25.553 | INFO    | Task run 'always_succeeds_task-c9014725-0' - Finished in state Completed()
21:01:25.577 | INFO    | Flow run 'vivid-chachalaca' - Finished in state Completed('I am happy with this result')
Completed(message='I am happy with this result', type=COMPLETED, result=None, flow_run_id=aa393122-66a6-4353-915e-1c4d2c2cdcbd)
```
</div>

### Return an object

If a flow returns any other Python object, the final state is always `Completed`.

```python hl_lines="10"
from prefect import task, flow

@task
def always_fails_task():
    raise ValueError("I am bad task")

@flow
def always_succeeds_flow():
    always_fails_task()
    return "foo"
```

Running this flow produces the following result.

<div class="terminal">
```bash
21:02:45.715 | INFO    | prefect.engine - Created flow run 'sparkling-pony' for flow 'always-succeeds-flow'
21:02:45.715 | INFO    | Flow run 'sparkling-pony' - Using task runner 'ConcurrentTaskRunner'
21:02:45.816 | INFO    | Flow run 'sparkling-pony' - Created task run 'always_fails_task-58ea43a6-0' for task 'always_fails_task'
21:02:45.853 | ERROR   | Task run 'always_fails_task-58ea43a6-0' - Encountered exception during execution:
Traceback (most recent call last):...
ValueError: I am bad task
21:02:45.879 | ERROR   | Task run 'always_fails_task-58ea43a6-0' - Finished in state Failed('Task run encountered an exception.')
21:02:46.593 | INFO    | Flow run 'sparkling-pony' - Finished in state Completed()
Completed(message=None, type=COMPLETED, result='foo', flow_run_id=7240e6f5-f0a8-4e00-9440-a7b33fb51153)
```
</div>

!!! note Returning multiple states
    When returning multiple states, they must be contained in a `set`, `list`, or `tuple`. If other collection types are used, the result of the contained states will not be checked.


