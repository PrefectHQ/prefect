---
description: Getting tasks to run in a desired order.
tags:
  - tasks
  - dependencies
  - wait_for
search:
  boost: 2
---

# Determining Upstream Dependencies

Return values from tasks can be used by other tasks and subflows to determine their upstream dependencies. Prefect uses upstream dependencies in two ways:

1. To populate dependency arrows in the flow run graph
2. To determine execution order for concurrently submitted units of work that depend on each other

For example, compare how submitting tasks to the `ConcurrentTaskRunner` behaves both with and without stating their upstream dependencies:

=== "Without dependencies"

    ```python
    @flow(log_prints=True) # Default task runner is ConcurrentTaskRunner
    def flow_of_tasks():
        # no dependencies, execution is order not guaranteed
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

=== "With dependencies"

    ```python
    @flow(log_prints=True) # Default task runner is ConcurrentTaskRunner
    def flow_of_tasks():
        # with dependencies, tasks execute in order
        first_result = first.submit()
        second_result = second.submit(first_result)
        third.submit(second_result)

    @task
    def first():
        print("I'm first!")

    @task
    def second(input):
        print("I'm second!")

    @task
    def third(input):
        print("I'm third!")
    ```

    ```text hl_lines="7 9 11"
    Flow run 'statuesque-waxbill' - Created task run 'first-0' for task 'first'
    Flow run 'statuesque-waxbill' - Submitted task run 'first-0' for execution.
    Flow run 'statuesque-waxbill' - Created task run 'second-0' for task 'second'
    Flow run 'statuesque-waxbill' - Submitted task run 'second-0' for execution.
    Flow run 'statuesque-waxbill' - Created task run 'third-0' for task 'third'
    Flow run 'statuesque-waxbill' - Submitted task run 'third-0' for execution.
    Task run 'first-0' - I'm first!
    Task run 'first-0' - Finished in state Completed()
    Task run 'second-0' - I'm second!
    Task run 'second-0' - Finished in state Completed()
    Task run 'third-0' - I'm third!
    Task run 'third-0' - Finished in state Completed()
    Flow run 'statuesque-waxbill' - Finished in state Completed('All states completed.')
    ```

A task or subflow's upstream dependencies can be inferred automatically via its inputs, or stated explicitly via the `wait_for` argument.

!!! note 
    **Only return values from tasks** inform Prefect's in-flow dependency capabilities. Return values from non-task-decorated functions, including subflows, do not carry the same information about their origin as return values from tasks.

## Automatic dependencies

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

## Manual dependencies

Tasks that do not share data can be informed of their upstream dependencies through the `wait_for` argument. Just as with automatic dependencies, this applies to calling task functions directly, calling [`.submit()`](/api-ref/prefect/tasks/#prefect.tasks.Task.submit), or calling [`.map()`](/api-ref/prefect/tasks/#prefect.tasks.Task.map).

!!! warning "Differences with `.map()`"
    Manually defined upstream dependencies apply to all tasks submitted by `.map()`, so each mapped task must wait for both `downstream_1` _and_ `downstream_2` to finish. This is distinct from automatic dependencies for mapped tasks, where each mapped task must only wait for the upstream tasks whose results it depends on.

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

## Upstream dependencies for subflows

Subflows will also wait to run if they are provided with task results, either as input or to `wait_for`. This is especially useful for ensuring subflows run after submitted tasks whose logic or data they may depend on.

=== "Without dependencies"
=== "Automatic dependencies"
=== "Manual dependencies"

