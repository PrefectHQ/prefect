---
description: Learn the basics of Prefect task runners and task execution within a flow.
tags:
    - tutorial
    - tasks
    - task runners
    - sequential execution
    - parallel execution
    - asynchronous execution
    - async
---

# Flow execution

Prefect allows you to configure many aspects of how your flows and tasks run - here we review execution configuration _within a single flow run_.  For topics such as scheduling and flow deployment configuration see the tutorial on [Deployments](/tutorials/deployments/).

## TaskRunners

Oftentimes we want our tasks to run in parallel or even on different machines for efficiency.  Prefect exposes this functionality via the concept of a _task runner_.

!!! note "Running flows in parallel requires no configuration"
    Note that task runners only manage _task runs_ within a single flow run - the ability to run multiple flow runs in parallel is default behavior in Prefect.  

Every time you call a task function, it is submitted to the flow's task runner for execution.  By default, Prefect uses a [`ConcurrentTaskRunner`][prefect.task_runners.ConcurrentTaskRunner], which will run your tasks concurrently.

If, however, we want our tasks to run in parallel (or sequentially) then we need to consider alternative approaches. 

## Parallel Execution

Achieving parallelism within a flow run is as simple as switching your task runner to Prefect's `DaskTaskRunner`; however please note that because the `DaskTaskRunner` uses multiprocessing, it can only be used when running interactively or when protected by an `if __name__ == "__main__":` guard when used in a script.

```python
import time

from prefect import task, flow
from prefect.task_runners import DaskTaskRunner

@task
def print_values(values):
    for value in values:
        time.sleep(0.5)
        print(value, end="\r")

@flow(task_runner=DaskTaskRunner())
def parallel_flow():
    print_values(["AAAA"] * 15)
    print_values(["BBBB"] * 10)

if __name__ == "__main__":
    parallel_flow()
```

When you run this flow you should see the terminal output randomly switching between `AAAA` and `BBBB` showing that these two tasks are indeed running in parallel.

!!! warning "The dask scheduler can be hard to predict"
    When using the `DaskTaskRunner`, Prefect is submitting each task run to a dask cluster object.  [The dask scheduler then determines when and how each individual run should be executed](https://distributed.dask.org/en/latest/scheduling-policies.html) (with the constraint that the order matches the execution graph that Prefect provided).  

    This means that the only way to _force_ dask to walk the task graph in a particular order is to configure Prefect dependencies between your tasks.

Read more about customizing Dask in our [Dask task runner tutorial](/tutorials/dask-ray-task-runners/#running-parallel-tasks-with-dask).

## Asynchronous Execution

Prefect supports asynchronous task and flow definitions.  All of [the standard rules of async](https://docs.python.org/3/library/asyncio-task.html) apply:

```python
import asyncio

from prefect import task, flow

@task
async def print_values(values):
    for value in values:
        await asyncio.sleep(1) # yield
        print(value, end=" ")

@flow
async def async_flow():
    await print_values([1, 2])  # runs immediately
    coros = [print_values("abcd"), print_values("6789")]

    # asynchronously gather the tasks
    await asyncio.gather(*coros)
```

When we run this flow, we find that the coroutines that were gathered yield control to one another and are run concurrently:

<div class="termy">
```
>>> asyncio.run(async_flow())
1 2 a 6 b 7 c 8 d 9
```
</div>

Asynchronous task execution is currently supported with all task runners.

!!! tip "Additional Reading"
    To learn more about the concepts presented here, check out the following resources:

    - [Task runners](/concepts/task_runners/)
