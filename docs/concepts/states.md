# States

## Overview

States are the "currency" of Prefect. All information about tasks and flows is transmitted via rich `State` objects. While you don't need to know the details of the state system to use Prefect, you can give your workflows superpowers by taking advantage of it.

At any moment, you can learn anything you need to know about a task or flow by examining its current state or the history of its states. For example, a state could tell you:

- that a task is scheduled to make a third run attempt in an hour
- that a task succeeded and what data it produced
- that a task is paused and waiting for a user to resume it
- that a task's output is cached and will be reused on future runs
- that a task failed because it timed out
- etc. etc.

By manipulating a relatively small number of task states, Prefect workflows can harness this emergent complexity.

## State objects

All `State` objects have three important characteristics: a `type`, `message`, and `result`. Some states have additional fields, as well. For example, a `Retrying` state has a field that says when the task should be retried.

### Messages

State messages usually explain _why_ the state was entered. In the case of `Failed` states, they often contain the error message associated with the failure.

```python
Success(message="The task succeeded!")
```

or

```python
Pending(message="This task is waiting to start")
```

### Results

State results carry data associated with the state. For task `Success` states, this is the data produced by the task. For `Failed` states, it is often the Python `Exception` object that led to the failure.

::: tip Failed results
Because all states have a `result` field, it means that tasks can work with the results of failed upstream tasks. This may seem surprising, but it's incredibly powerful. For example, a task that runs after a failed task could look at the failed result to see exactly why the failure took place. A task following a skipped task could receive a message indicating why the task was skipped.

To be clear: the default trigger will not run tasks that follow failed tasks, so users will have to opt-in to this functionality.
:::

## State types

There are three main states: `Pending`, `Running`, and `Finished`. Flows and tasks typically progress through these three states. At each stage of the execution pipeline, the current state determines what actions are taken. For example, if you attempt to run a task in a `Success` state (a type of `Finished`) it will simply exit the pipeline without changing. If you attempt to run a task in a `Retrying` state (a type of `Pending`), it will proceed as long as the state's scheduled retry time has already passed.
