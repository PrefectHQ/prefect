---
description: Prefect states contain information about the status of a flow or task run.
tags:
    - orchestration
    - flow runs
    - task runs
    - states
    - status
---

# States

## Overview
States are rich objects that contain information about the status of a particular [task](../tasks) run or [flow](../flows/) run. While you don't need to know the details of the states to use Prefect, you can give your workflows superpowers by taking advantage of it.

At any moment, you can learn anything you need to know about a task or flow by examining its current state or the history of its states. For example, a state could tell you:

-   that a task is scheduled to make a third run attempt in an hour
-   that a task succeeded and what data it produced
-   that a task was scheduled to run, but later cancelled
-   that a task used the cached result of a previous run instead of re-running
-   that a task failed because it timed out

By manipulating a relatively small number of task states, Prefect flows can harness the complexity that emerges in workflows. 

!!! note "Only runs have states"
    Though we often refer to the "state" of a flow or a task, what we really mean is the state of a flow _run_ or a task _run_. Flows and tasks are templates that describe what a system does; only when we run the system does it also take on a state. So while we might refer to a task as "running" or being "successful", we really mean that a specific instance of the task is in that state.

## State Types
States have names and types. State types are canonical, with specific orchestration rules that apply to transitions into and out of each state type. A state's name, is often, but not always, synonymous with its type. For example, a task run that is running for the first time has a state with the name Running and the type `RUNNING`. However, if the task retries, that same task run will have the name Retrying and the type `RUNNING`. Each time the task run transitions into the `RUNNING` state, the same orchestration rules are applied.

There are terminal state types from which there are no orchestrated transitions to any other state type.

- `COMPLETED`
- `CANCELLED`
- `FAILED`
- `CRASHED`

The full complement of states and state types includes:
  
| Name | Type | Terminal? | Description
| --- | --- | --- | --- |
| Scheduled | SCHEDULED | No | The run will begin at a particular time in the future. |
| Late | SCHEDULED | No | The run's scheduled start time has passed, but it has not transitioned to PENDING (5 seconds by default). |
| <span class="no-wrap">AwaitingRetry</span> | SCHEDULED | No | The run did not complete successfully because of a code issue and had remaining retry attempts. |
| Pending | PENDING | No | The run has been submitted to run, but is waiting on necessary preconditions to be satisfied. |
| Running | RUNNING | No | The run code is currently executing. |
| Retrying | RUNNING | No | The run code is currently executing after previously not complete successfully. |
| Cancelled | CANCELLED | Yes | The run did not complete because a user determined that it should not. |
| Completed | COMPLETED | Yes | The run completed successfully. |
| Failed | FAILED | Yes | The run did not complete because of a code issue and had no remaining retry attempts. |
| Crashed | CRASHED | Yes | The run did not complete because of an infrastructure issue. |

## Returned values

When calling a task or a flow, there are three types of returned values:

- Data: A Python object (such as `int`, `str`, `dict`, `list`, and so on).
- `State`: A Prefect object indicating the state of a flow or task run.
- [`PrefectFuture`](/api-ref/prefect/futures/#prefect.futures.PrefectFuture): A Prefect object that contains both _data_ and _State_.

Returning data  is the default behavior any time you call `your_task()`.

Returning Prefect [`State`](/api-ref/orion/schemas/states/) occurs anytime you call your task or flow with the argument `return_state=True`.

Returning [`PrefectFuture`](/api-ref/prefect/futures/#prefect.futures.PrefectFuture) is achieved by calling `your_task.submit()`.

### Return Data

By default, running a task will return data:

```python hl_lines="3-5"
from prefect import flow, task 

@task 
def add_one(x):
    return x + 1

@flow 
def my_flow():
    result = add_one(1) # return int
```

The same rule applies for a subflow:

```python hl_lines="1-3"
@flow 
def subflow():
    return 42 

@flow 
def my_flow():
    result = subflow() # return data
```

### Return Prefect State

To return a `State` instead, add `return_state=True` as a parameter of your task call.

```python hl_lines="3-4"
@flow 
def my_flow():
    state = add_one(1, return_state=True) # return State
```

To get data from a `State`, call `.result()`.

```python hl_lines="4-5"
@flow 
def my_flow():
    state = add_one(1, return_state=True) # return State
    result = state.result() # return int
```

The same rule applies for a subflow:

```python hl_lines="7-8"
@flow 
def subflow():
    return 42 

@flow 
def my_flow():
    state = subflow(return_state=True) # return State
    result = state.result() # return int
```

### Return a PrefectFuture

To get a `PrefectFuture`, add `.submit()` to your task call.

```python hl_lines="3-5"
@flow 
def my_flow():
    future = add_one.submit(1) # return PrefectFuture
```

To get data from a `PrefectFuture`, call `.result()`.

```python hl_lines="4-5"
@flow 
def my_flow():
    future = add_one.submit(1) # return PrefectFuture
    result = future.result() # return data
```

To get a `State` from a `PrefectFuture`, call `.wait()`.

```python hl_lines="4-5"
@flow 
def my_flow():
    future = add_one.submit(1) # return PrefectFuture
    state = future.wait() # return State
```
## Final state determination

The final state of a flow is determined by its return value.  The following rules apply:

- If an exception is raised directly in the flow function, the flow run is marked as `FAILED`.
- If the flow does not return a value (or returns `None`), its state is determined by the states of all of the tasks and subflows within it.
    - If _any_ task run or subflow run failed and none were cancelled, then the final flow run state is marked as `FAILED`.
    - If _any_ task run or subflow run was cancelled, then the final flow run state is marked as `CANCELLED`.
- If a flow returns a manually created state, it is used as the state of the final flow run. This allows for manual determination of final state.
- If the flow run returns _any other object_, then it is marked as successfully completed.

See the [Final state determination](/concepts/flows/#final-state-determination) section of the [Flows](/concepts/flows/) documentation for further details and examples.
