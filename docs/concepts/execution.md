# Execution

Prefect's execution model is built around a concept called `State`. Information is communicated between tasks and flows via `State` objects, and users have a variety of ways to affect and interact with the system's state.

## States

Tasks and Flows all operate on `State` objects. A `State` always has a `type`, and may also have a `message` and `result`. Some states carry additional inforamtion, as well.

### State Types

Prefect components reflect status by updating the `type` of their state. There are three basic types: `Pending`, `Running`, and `Finished`. Prefect exposes a rich state vocabulary by building on top of these three. The most common states are:

- Scheduled
- Pending
- Running
- Success
- Failed
- Retry
- Skipped
- Cached

When flows or tasks are executed, the current `State` is evaluated to determine what actions are possible. For example, a `Pending` task can be put in a `Running` state, but a `Failed` task can not. `Failed` tasks can be put in `Retry` states, however, and because `Retry` is a type of `Pending`, that task can be run later.

::: warning Common classes
The same `State` objects are used for `Flows` and `Tasks`, though not all states are applicable to both. In addition, `Flows` and `Tasks` may respond to states in different ways.
:::

### State Messages

State messages are purely informative. A message is usually used to explain _why_ a certain state was entered. For example, a flow might return

```python
Failed(message='Some tasks failed.')
```

or

```python
Success(message='All tasks succeeded.')
```

### State Results

States may carry optional result values. Most often, this is the mechanism by which tasks exchange data.

### Other Attributes

States may have additional attributes. For example, `Retry` states may contain a `retry_time`; states that involve caching will contain relevant details; etc.

## Running a flow

Prefect provides `FlowRunner` for running flows and `TaskRunner` classes for running tasks. In general, users should prefer `flow.run()` as a convenience method that automatically creates a `FlowRunner` and submits the flow for execution.

### Retrieving flow state

When a flow is run, it returns a [`State`](#state) object indicating the result of the run.

```python
with Flow:
    t = FunctionTask(lambda: 1)

flow_state = flow.run()
```

### Retrieving task states

By default, flows do not return the states of any tasks when run. If you would like to inspect task states, add a `return_tasks` argument to `flow.run()` containing a list of desired tasks. The `flow_state` will now have a `result` attribute that is a dictionary of `{Task: State}` pairs indicating the state of each requested task.

```python
with Flow():
    t = FunctionTask(lambda: 1)

flow_state = flow.run(return_tasks=[t])
task_state = flow_state.result[t]
assert task_state.result == 1
```

::: warning Limiting return_tasks
For small flows, returning a state for every task is totally fine. However, retrieving the state of every task of a large flow could produce an enormous amount of data. As best practice, only retrieve task states you need.
:::

## Caching

Prefect provides a few ways to work with cached data. Wherever possible, caching is handled automatically or with minimal user input.

### Input Caching

When running a Prefect flow, it's common to have tasks that will need to be re-run in the future. For example, this could happen when a task fails and needs to be retried, or when a task has a `manual_only` trigger.

Whenever Prefect detects that a task will need to be run in the future, it automatically caches any information that the task needs to run and stores it on the resulting `State`. The next time Prefect encounters the task, the critical information is deserialized and used to run the task.

::: tip Automatic caching
Input caching is an automatic caching. Prefect will automatically apply it whenever necessary.
:::

### Output Caching ("Time Travel")

Sometimes, it's desirable to cache the output of a task to avoid recomputing it in the future. Common examples of this pattern include expensive or time-consuming computations that are unlikely to change. In this case, users can indicate that a task should be cached for a certain duration or as long as certain conditions are met.

This mechanism is sometimes called "Time Travel" because it makes results computed in one flow run available to other runs.

Output caching is controlled with two `Task` arguments: `cache_for` and `cache_validator`.

- `cache_for`: a `timedelta` indicating how long the output should be cached
- `cache_validator`: a `callable` indicating how the cache should be expired. The default is `duration_only`, meaning the cache will be active for the duration of `cache_for`. Other validators can be found in `prefect.engine.cache_validators` and include mechanisms for invalidating the cache if the task receives different inputs or if the flow is run with different parameters.

```python
# this task will be cached for 1 hour
task_1 = prefect.Task(
    cache_for=datetime.timedelta(hours=1))

# this task will be cached for 1 hour, but only if the flow is run with the same parameters
task_2 = prefect.Task(
    cache_for=datetime.timedelta(hours=1),
    cache_validator=prefect.engine.cache_validators.all_parameters)
```

## Triggers

When Prefect creates a dependency between two tasks, it always creates a "state dependency." Sometimes, a "data dependency" is also created. With a state dependency, the downstream task will not run unless its trigger function permits the state of the upstream task.

The default trigger is `all_successful`, meaning a downstream task won't run unless all upstream tasks report `Success` states. By changing the trigger function, you can control a task's behavior with regard to its upstream tasks. Other triggers include `all_failed`, `any_successful`, `any_failed`, `all_finished` and `manual_only`. These can be used to create tasks that only run when preceding tasks fail, or run no matter what, or never run automatically at all!

Tasks will only evaluate their triggers if all upstream tasks are in `Finished` states. Therefore, the `all_finished` trigger is the same as an `always_run` trigger.

::: tip Use a manual_only trigger to pause a flow
The `manual_only` trigger always fails, so the flow will never run a `manual_only` task automatically. This allows users to pause a flow mid-run. To resume, pass the `manual_only` task as one of the run's `start_tasks`. This will treat is as a root task with no upstream tasks, and skip the trigger check entirely.
:::

## Signals

Prefect does its best to infer the state of a running task. If the `run()` method succeeds, Prefect sets the state to `Success` and records any data that was returned. If the `run()` method raises an error, Prefect sets the state to `Failed` with an appropriate message.

Sometimes, you may want finer control over a task's state. For example, you may want a task to be skipped or to force a task to retry. In that case, raise the appropriate Prefect `signal`. It will be intercepted and transformed into the appropriate state.

Prefect provides signals for most states, including `RETRY`, `SKIP`, `FAILED`, and `SUCCESS`.

```python
from prefect import task
from prefect.engine import signals

def retry_if_negative(x):
    if x < 0:
        raise signals.RETRY()
    else:
        return x
```

Another common use of Prefect signals is when the task in question will be nested under other functions that could intercept its normal result or error. In that case, a signal could be used to "bubble up" a desired state change and bypass the normal return mechanism.

## Context

Prefect provides a powerful `Context` object to share information without requiring explicit arguments on a task's `run()` method.

The `Context` can be accessed at any time, and will be pre-populated with information before and during each flow run.

```python
@task
def try_unlock():
    if prefect.context.key == 'abc':
        return True
    else:
        raise signals.FAIL()

with Flow() as flow:
    try_unlock()

flow.run() # this run fails

with prefect.context(key='abc'):
    flow.run() # this run is successful
```
