---
sidebarDepth: 0
---

# Next Steps

In the [introduction](thinking-prefectly.md), we took a look at creating tasks and combining them into flows. Prefect's functional and imperative APIs make that easy, but the result was a fairly vanilla data pipeline. In this section, we're going to explore how Prefect enables advanced mechanisms for overlaying complex business logic on your workflow.


You can also check out our [full tutorial](/core/tutorial/01-etl-before-prefect.html) on building real-world data applications.


## Triggers

So far, we've dealt exclusively with tasks that obey "normal" data pipeline rules: whenever a task succeeds, its downstream dependencies start running.

It is frequently desirable to build flows in which tasks respond to each other in more complicated ways. A simple example is a "clean up task" that must run, even (or only!) if a prior task failed. Suppose our first task creates a Spark cluster, the second task submits a job to that cluster, and a third task tears down the cluster. In a "normal" pipeline world, if the second task fails the third task won't run -- and that could result in our Spark cluster running forever!

Prefect introduces a concept called [`triggers`](../concepts/execution.html#triggers) to solve this situation. Before a task runs, its trigger function is called on a set of upstream task states. If the trigger function doesn't pass, the task won't run. Prefect has a variety of built-in triggers, including `all_successful` (the default), `all_failed`, `any_successful`, `any_failed`, and even a particularly interesting one called `manual_only`.

Let's set up our Spark cluster flow, using obvious pseudocode where appropriate:

```python
from prefect import task, Flow

@task
def create_cluster():
    cluster = create_spark_cluster()
    return cluster

@task
def run_spark_job(cluster):
    submit_job(cluster)

@task
def tear_down_cluster(cluster):
    tear_down(cluster)


with Flow("Spark") as flow:
    # define data dependencies
    cluster = create_cluster()
    submitted = run_spark_job(cluster)
    result = tear_down_cluster(cluster)

    # wait for the job to finish before tearing down the cluster
    result.set_upstream(submitted)

```

When we run this flow, everything will work perfectly as long as the Spark job runs successfully. However, if the job fails, then the `submitted` task will enter a `Failed` state. Because the default trigger on the `tear_down_cluster` task is `all_successful`, it will enter a `TriggerFailed` state -- a special variant of `Failed` that indicates that the trigger, not a runtime error, was the cause.

To fix this, we simply adjust the trigger when defining the task. In this case we can use the `always_run` trigger, which is an alias for `all_finished`:

```python
@task(trigger=prefect.triggers.always_run)  # one new line
def tear_down_cluster(cluster):
    tear_down(cluster)
```

All other code remains the same. Now the `tear_down_cluster` task will *always* run, even -- or especially -- when the `submitted` task fails.

::: tip Tasks never run before upstream tasks finish
Prefect will never run a task before its upstream tasks finish. This is why the `all_finished` and `always_run` triggers are synonymous.
:::

## Reference Tasks

Previously, we used a trigger to ensure that our `tear_down_cluster` task always runs. Let's choose to live in a world in which it always runs successfully. This actually presents a problem, because workflow management systems generally set the state of the entire workflow from the state of the terminal tasks. In this case, our terminal task, `tear_down_cluster`, is going to run and succeed even if the job we wanted to run fails!

This illustrates an important issue: workflow management systems, and workflows in general, have semantics that are not necessarily aligned with business logic. In this case, we definitely want to consider the flow to have *failed* if the job didn't run, but we also want the workflow itself -- including the clean up task -- to *succeed!*

Prefect introduces a mechanism called "reference tasks" to solve this conundrum. Flows remain in a `Running` state until all of their tasks enter `Finished` states. At that time, the Flow essentially decides its own final state by applying an `all_successful` trigger to its reference tasks. By default, the reference tasks are the terminal tasks, but users can set them to be any tasks they want.

In our case, we make a simple tweak at the end of our script to tell this flow to use the `run_spark_job` task as its reference task:

```python
flow.set_reference_tasks([submitted])
```

Now the flow's state will be determined by what happens to this job. If it fails, the flow state will fail *even after the clean up task succeeds*.

## Signals

Prefect's [State](../concepts/states.html) system allows users to set up advanced behaviors through triggers and reference tasks. Each task enters a final state based on what happens in its `run()` function: if the function finishes normally, the task enters a `Success` state; and if the function encounters an error, the task enters a `Failed` state. However, Prefect also gives users fine-grained control over a task's state via a mechanism called "signals."

Signals are ways of telling the Prefect engine that a task should be moved immediately into a specific state.

For example, at any time, a task could raise a `SUCCESS` signal to succeed before its `run()` function would normally finish. Conversely, it could raise a `FAILED` signal if the user wanted more careful control about the resulting `Failed` state.

There are other, more interesting signals available. For example, raising a `RETRY` signal will cause a task to immediately retry itself, and raising a `PAUSE` signal will enter a `Paused` state until the task is explicitly resumed.

Another useful signal is the `SKIP` signal. When a task is skipped, downstream tasks are also skipped unless they specifically set `skip_on_upstream_skip=False`. This means that users can set up entire workflow branches that can be skipped if a condition isn't met.

::: tip SKIP is treated like SUCCESS
When a task is skipped, it's usually treated as if it ran successfully. This is because tasks only skip if users specifically introduce skipping logic, so the result is compliant with the user's design.
:::

To raise a signal, simply use it inside your task's run() function:

```python
from prefect.engine import signals

@task
def signal_task(message):
    if message == 'go!':
        raise signals.SUCCESS(message='going!')
    elif message == 'stop!':
        raise signals.FAIL(message='stopping!')
    elif message == 'skip!':
        raise signals.SKIP(message='skipping!')
```

If the message passed to this task is `"stop!"`, then the task will fail.
