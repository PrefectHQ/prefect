---
description: Getting tasks to run in a desired order.
tags:
  - tasks
  - dependencies
  - wait_for
search:
  boost: 2
---

# Managing Task Dependencies

Submitting tasks to any [task runner](/concepts/task-runners/) besides the `SequentialTaskRunner` enables them to run simultaneously. Doing this without managing your task's upstream dependencies means their order isn't guaranteed:

```python
@flow(log_prints=True) # Default task runner is ConcurrentTaskRunner
def flow_of_tasks():
    first.submit()
    second.submit()
    third.submit()

@task
def first():
    print("I'm first!")

@task
def second():
    print("I'm second!")

@task
def third():
    print("I'm third!")
```

```text hl_lines="7-9"
Flow run 'pumpkin-puffin' - Created task run 'first-0' for task 'first'
Flow run 'pumpkin-puffin' - Submitted task run 'first-0' for execution.
Flow run 'pumpkin-puffin' - Created task run 'second-0' for task 'second'
Flow run 'pumpkin-puffin' - Submitted task run 'second-0' for execution.
Flow run 'pumpkin-puffin' - Created task run 'third-0' for task 'third'
Flow run 'pumpkin-puffin' - Submitted task run 'third-0' for execution.
Task run 'third-0' - I'm third!
Task run 'first-0' - I'm first!
Task run 'second-0' - I'm second!
Task run 'second-0' - Finished in state Completed()
Task run 'third-0' - Finished in state Completed()
Task run 'first-0' - Finished in state Completed()
Flow run 'pumpkin-puffin' - Finished in state Completed('All states completed.')
```

Upstream dependencies can be inferred automatically via a task's inputs and return values, or stated explicitly via a task's `wait_for` argument.

This dependency information is used by Prefect in two ways:

1. For populating dependency arrows in the flow run graph
2. For determining task execution order when using non-sequential task runners

## Automatic Dependencies

When a result from an upstream task is used as input for another task, Prefect automatically determines that the task producing the result is an upstream dependency of the task that uses its result as input.

This is true for every way you can run tasks with Prefect, whether you're calling the task function directly, calling [`.submit()`](/api-ref/prefect/tasks/#prefect.tasks.Task.submit), or calling [`.map()`](/api-ref/prefect/tasks/#prefect.tasks.Task.map).

```python
from prefect import flow, task


@flow(log_prints=True)
def flow_of_tasks():
    upstream_result = upstream.submit()
    downstream_1_result = downstream_1.submit(upstream_result)
    downstream_2_result = downstream_2.submit(upstream_result)
    mapped_task_results = mapped_task.map([downstream_1_result, downstream_2_result])
    final_task(mapped_task_results)

@task
def upstream():
    return "Hello from upstream!"

@task
def downstream_1(input):
    return input

@task
def downstream_2(input):
    return input

@task
def mapped_task(input):
    return input

@task
def final_task(input):
    print(input)
```

![Flow run graph for automatic task dependencies](/img/guides/automatic-task-dependencies.png)

## Manual Dependencies

Tasks that do not share data can be informed of their upstream dependencies through the `wait_for` argument. Just as with automatic dependencies, this applies to calling task functions directly, calling [`.submit()`](/api-ref/prefect/tasks/#prefect.tasks.Task.submit), or calling [`.map()`](/api-ref/prefect/tasks/#prefect.tasks.Task.map).

!!! tip "Differences with `.map()`"
    Note that manually defined upstream dependencies apply to all tasks submitted by `.map()`, so each mapped task must wait for both `downstream_1` _and_ `downstream_2` to finish. This is distinct from automatic dependencies for mapped tasks, where each mapped task must only wait for the upstream tasks whose results it depends on.

```python
from prefect import flow, task


@flow(log_prints=True)
def flow_of_tasks():
    upstream_result = upstream.submit()
    downstream_1_result = downstream_1.submit(wait_for=[upstream_result])
    downstream_2_result = downstream_2.submit(wait_for=[upstream_result])
    mapped_task_results = mapped_task.map([1, 2], wait_for=[downstream_1_result, downstream_2_result])
    final_task(wait_for=mapped_task_results)

@task
def upstream():
    pass

@task
def downstream_1():
    pass

@task
def downstream_2():
    pass

@task
def mapped_task(input):
    pass

@task
def final_task():
    pass
```

![Flow run graph for manual task dependencies](/img/guides/manual-task-dependencies.png)