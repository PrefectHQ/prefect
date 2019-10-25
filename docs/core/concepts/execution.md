# Execution

Within the Prefect engine, there are many ways for users to affect execution.

[[toc]]

## Triggers

Trigger functions decide if a task is ready to run, based on the states of the upstream tasks. Prefect tasks won't run unless their triggers pass.

By default, tasks have an `all_successful` trigger, meaning they won't run unless all upstream tasks were successful. By changing the trigger function, you can control a task's behavior with regard to its upstream tasks. Other triggers include `all_failed`, `any_successful`, `any_failed`, `all_finished` and `manual_only`. These can be used to create tasks that only run when preceding tasks fail, or run no matter what, or never run automatically at all!

Tasks will only evaluate their triggers if all upstream tasks are in `Finished` states. Therefore, the `all_finished` trigger is the same as an `always_run` trigger.

::: tip Use a manual_only trigger to pause a flow
The `manual_only` trigger always puts the task in a `Paused` state, so the flow will never run a `manual_only` task automatically. This allows users to pause a flow mid-run. To resume, put the task in a `Resume` state and set it as one of the run's `start_tasks`. This will treat is as a root task with no upstream tasks, and skip the trigger check entirely.
:::

For example, suppose we want to construct a flow with one root task; if this task
succeeds, we want to run task B.  If instead it fails, we want to run task C.  We
can accomplish this pattern through the use of triggers:

```python
import random

from prefect.triggers import all_successful, all_failed
from prefect import task, Flow


@task(name="Task A")
def task_a():
    if random.random() > 0.5:
        raise ValueError("Non-deterministic error has occured.")

@task(name="Task B", trigger=all_successful)
def task_b():
    # do something interesting
    pass

@task(name="Task C", trigger=all_failed)
def task_c():
    # do something interesting
    pass


with Flow("Trigger example") as flow:
    success = task_b(upstream_tasks=[task_a])
    fail = task_c(upstream_tasks=[task_a])

## note that as written, this flow will fail regardless of the path taken
## because *at least one* terminal task will fail;
## to fix this, we want to set Task B as the "reference task" for the Flow
## so that it's state uniquely determines the overall Flow state
flow.set_reference_tasks([success])

flow.run()
```

## State signals

Prefect does its best to infer the state of a running task. If the `run()` method succeeds, Prefect sets the state to `Success` and records any data that was returned. If the `run()` method raises an error, Prefect sets the state to `Failed` with an appropriate message.

Sometimes, you may want more fine control over a task's state. For example, you may want a task to be skipped or to force a task to retry. In that case, raise the appropriate Prefect `signal`. It will be intercepted and transformed into the appropriate state.

Prefect provides signals for most states, including `RETRY`, `SKIP`, `FAIL`, `SUCCESS`, and `PAUSE`.

```python
from prefect import task
from prefect.engine import signals

def retry_if_negative(x):
    if x < 0:
        raise signals.RETRY()
    else:
        return x
```

Another common use of Prefect signals is when the task in question will be nested under other functions that could trap its normal result or error. In that case, a signal could be used to "bubble up" a desired state change and bypass the normal return mechanism.

## Context

Prefect provides a powerful `Context` object to share information without requiring explicit arguments on a task's `run()` method.

The `Context` can be accessed at any time, and will be pre-populated with information before and during each flow run. For an exhaustive list of values that you can find in context, see the corresponding [API documentation](../../api/unreleased/utilities/context.html).

```python
@task
def try_unlock():
    if prefect.context.key == 'abc':
        return True
    else:
        raise signals.FAIL()

with Flow('Using Context') as flow:
    try_unlock()

flow.run() # this run fails

with prefect.context(key='abc'):
    flow.run() # this run is successful
```

::: warning Modifying the context
We strongly recommend that users treat the context as read-only. Modifications can have unintended consequences.
:::
