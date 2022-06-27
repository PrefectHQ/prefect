# Execution

Within the Prefect engine, there are many ways for users to affect execution.

[[toc]]

## Triggers

Trigger functions decide if a task is ready to run, based on the states of the upstream tasks. Prefect tasks won't run unless their triggers pass.

By default, tasks have an `all_successful` trigger, meaning they won't run unless all upstream tasks were successful. By changing the trigger function, you can control a task's behavior with regard to its upstream tasks. Other triggers include `all_failed`, `any_successful`, `any_failed`, `all_finished` and `manual_only`. These can be used to create tasks that only run when preceding tasks fail, or run no matter what, or never run automatically at all!

Tasks will only evaluate their triggers if all upstream tasks are in `Finished` states. Therefore, the `all_finished` trigger is the same as an `always_run` trigger.

!!! tip Use a manual_only trigger to pause a flow
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
        raise ValueError("Non-deterministic error has occurred.")

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

The `Context` can be accessed at any time, and Prefect will populate it with information during flow and task execution. The context object itself can be populated with any arbitrary user-defined key-value pair, which in turn can be accessed with dot notation or with dictionary-like indexing. For example, the following code assumes a user has provided the context `a=1` , and can access it one of three ways:

```python
>>> import prefect
>>> prefect.context.a
1
>>> prefect.context['a']
1
>>> prefect.context.get('a')
1
```

### Adding context globally
Adding context globally is possible via your `config.toml` in a section called `[context]`. For any keys specified here, as long as Prefect Core does not override this key internally, it will be accessible globally from `prefect.context`, even outside of a flow run.
```
# config.toml
[context]
a = 1
```

```python
>>> import prefect
>>> prefect.context.a
1
```

### Modifying context at runtime
Modifying context, even globally set context keys, at specific times is possible using a provided context manager:
```python
>>> import prefect
>>> with prefect.context(a=2):
...    print(prefect.context.a)
...
2
```

This is often useful to run flows under different situations for rapid iterative development:

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

### Prefect-supplied context
In addition to your own context keys, Prefect supplies context to the context object dynamically during flow runs and task runs. This context provides some standard information about the current flow or task. For example, running tasks already know about the day they are run from Prefect-provided context:
 
```python{4}
@task
def report_start_day():
    logger = prefect.context.get("logger")
    logger.info(prefect.context.today)

with Flow('My flow') as flow:
	report_start_day()

flow.run()
```
```text{5}
[2020-03-02 22:15:58,779] INFO - prefect.FlowRunner | Beginning Flow run for 'My flow'
[2020-03-02 22:15:58,780] INFO - prefect.FlowRunner | Starting flow run.
[2020-03-02 22:15:58,786] INFO - prefect.TaskRunner | Task 'report_start_time': Starting task run...
[2020-03-02 22:15:58,786] INFO - prefect.Task: report_start_day | 2020-03-02
[2020-03-02 22:15:58,788] INFO - prefect.TaskRunner | Task 'report_start_time': finished task run for task with final state: 'Success'
[2020-03-02 22:15:58,789] INFO - prefect.FlowRunner | Flow run SUCCESS: all reference tasks succeeded
```
Using this context can be useful to write time-aware tasks, such as tasks that trigger future work respective to its start time using `prefect.context.tomorrow` or processing only the prior day's data by using `prefect.context.yesterday`.

!!! tip What else is in context?
    For an exhaustive list of values that you can find in context, see the corresponding [API documentation](../../api/latest/utilities/context.html).
:::

!!! warning Caveats to modifying Prefect-supplied context
    Since Prefect uses some context internally to track metadata during the flow and task run logic, modifying Prefect-supplied context keys can have unintended consequences. It is recommended to generally avoid overriding the key names described in the API documentation.

    One exception to this is the timestamp related keys such as `prefect.context.today`. Users may wish to modify this context per flow run in order to implement "backfills", where individual flow runs execute on a subset of timeseries data.
:::
