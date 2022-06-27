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

!!! tip Only runs have states
    Though we often refer to the "state" of a flow or a task, what we really mean is the state of a flow _run_ or a task _run_. Flows and tasks are templates that describe what a system does; only when we run the system does it also take on a state. So while we might refer to a task as "running" or being "successful", we really mean that a specific instance of the task is in that state.
:::

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

!!! tip Failed results
    Because all states have a `result` field, it means that tasks can work with the results of failed upstream tasks. This may seem surprising, but it's incredibly powerful. For example, a task that runs after a failed task could look at the failed result to see exactly why the failure took place. A task following a skipped task could receive a message indicating why the task was skipped.

    To be clear: the default trigger will not run tasks that follow failed tasks, so users will have to opt-in to this functionality.
:::

## State types

There are three main types of states: `Pending`, `Running`, and `Finished`. Flows and tasks typically progress through them in that order, possibly more than once. Each state type has many children. For example, `Scheduled` and `Retrying` are both `Pending` states; `Success` and `Failed` are both `Finished` states.

At each stage of the execution pipeline, the current state determines what actions are taken. For example, if you attempt to run a task in a `Success` state it will exit the pipeline, because `Finished` states are never re-run. If you attempt to run a task in a `Retrying` state, it will proceed only as long as the state's scheduled retry time has already passed. In this way, states carry all of the critical information the Prefect engine uses to make decisions about workflow logic.

!!! tip Meta-states
    There's actually a fourth kind of state, called a `MetaState`, but it doesn't affect the execution pipeline. Instead, meta-states are used by Prefect to enhance existing states with additional information. For example, two meta-states are `Submitted` and `Queued`. These are used to "wrap" other states in a way that makes the original state recoverable. For example, a `Scheduled` state might be put into a `Submitted` state to indicate that it's been submitted for execution, but the original `Scheduled` state is needed by the engine to perform runtime logic. By wrapping the `Scheduled` state with the `Submitted` meta-state, rather than replacing it, the engine is able to recover the original information it needs.
:::

## State handlers & callbacks

It is often desirable to take action when a certain event happens, for example when a task fails. Prefect provides `state_handlers` for this purpose. Flows and Tasks may have one or more state handler functions that are called whenever the task's state changes. The signature of a state handler is:

```python
    def state_handler(obj: Union[Flow, Task], old_state: State, new_state: State) -> State:
        return new_state
```

Whenever the task's state changes, the handler will be called with the task itself, the old (previous) state, and the new (current) state. The handler must return a `State` object, which is used as the task's new state. This provides an opportunity to either react to certain states or even modify them. If multiple handlers are provided, then they are called in sequence with the state returned by one becoming the `new_state` value of the next.

For example, to send a notification whenever a task is retried:

```python
from prefect.engine import state

def notify_on_retry(task, old_state, new_state):
    if isinstance(new_state, state.Retrying):
        send_notification() # function that sends a notification
    return new_state

task_that_notifies = Task(state_handlers=[notify_on_retry])
```

## Flow state transitions

Flows transition through a relatively small number of states.

`Scheduled -> Running -> Success / Failed`

Typically, flow runs begin in a `Scheduled` state that indicates when the run should start. `Scheduled` is a subclass of `Pending`. When the run begins, it transitions in to a `Running` state. Finally, when all terminal tasks are finished, the flow moves to a `Finished` state. The final state will either be `Success` or `Failed`, depending on the states of the reference tasks.

## Task state transitions

Tasks transition through a much greater variety of states, as their execution can lead to many different outcomes. In general, they will repeatedly move from `Pending` states to `Running` states until they finally enter a `Finished` state.

While tasks can move through any combination of states, the following patterns are most common.

### Success

`Pending -> Running -> Success`

The most common pattern for tasks is to be created in a pending state, run, and succeed.

### Failure

`Pending -> Running -> Failed`

The second most common pattern is for tasks to encounter an error while running and end up in a `Failed` state.

### Failure (before running)

`Pending -> TriggerFailed`

If a task's trigger function doesn't return `True`, then the task will fail before it even runs, ending up in a `TriggerFailed` state.

### Retry

`Failed -> Retrying -> Running`

From a `Failed` state, appropriately configured tasks can automatically move into a `Retrying` state. Once the specified amount of time has passed, the task will move back into a `Running` state.

### Skip (while running)

`Running -> Skipped`

Users can cause tasks to skip themselves by raising a `SKIP` signal. Skipped states are generally treated as success states, with some additional caveats. For example, tasks downstream of skipped tasks will automatically skip themselves by default.

### Skip (before running)

`Pending -> Skipped`

If an upstream task is `Skipped` and a task has `skip_on_upstream_skip=True` (the default setting), then it will automatically skip itself before it runs. This allows users to bypass entire chains of tasks without needing to configure each one.

## Special task state transitions

Tasks also have more some unusual but important state transition patterns.

### Pause transition (while running)

`Running -> Paused -> Resume -> Running`

Users can pause tasks by raising a `PAUSE` signal. Once paused, tasks must be put in a `Resume` state in order to move back into a running state. Both `Paused` and `Resume` are subclasses of `Pending`

### Pause transition (before running)

`Pending -> Paused`

Tasks will also enter a paused state if they have a `manual_only` trigger. This will happen before they run, and users will have to explicitly start those tasks to continue.

### Mapped transition

`Running -> Mapped`

If a task is mapped over its inputs, then it will enter a `Mapped` state after it runs. This indicates that it did not do any work, but rather dynamically generated children tasks to carry out the mapped function. The children states can be accessed as `Mapped.map_states`. `Mapped` is a `Finished` state that subclasses `Success`.
