# Flow Execution

Prefect allows you to configure many aspects of how your flows and tasks run - here we review execution configuration _within a single flow run_.  For things like scheduling and flow deployment configuration see the tutorial on [Deployments](/tutorials/deployments/).

## Executors

Oftentimes we want our tasks to run in parallel or even on different machines for efficiency.  Prefect exposes this functionality via the concept of an _executor_.

!!! note "Running flows in parallel requires no configuration"
    Note that executors only manage _task runs_ within a single flow run - the ability to run multiple flow runs in parallel is default behavior in Prefect.  

Every time you call a task function, it is submitted to the flow's executor for execution.  By default, Prefect uses a [`SequentialExecutor`][prefect.executors.SequentialExecutor] that blocks and runs tasks in sequence as they are called.  For many situations, this is perfectly acceptable.

If, however, we want our tasks to run in parallel (or asynchronously) then we need to consider alternative approaches. 

## Parallel Execution

Achieving parallelism within a flow run is as simple as switching your executor to Prefect's `DaskExecutor`:

```python
import time
from prefect.executors import DaskExecutor

@task
def print_values(values):
    for value in values:
        time.sleep(0.5)
        print(value, end="\r")

@flow(executor=DaskExecutor())
def parallel_flow():
    print_values(["AAAA"] * 15)
    print_values(["BBBB"] * 10)
```

When you run this flow you should see the terminal output randomly switching between `AAAA` and `BBBB` showing that these two tasks are indeed running in parallel.

!!! warning "The dask scheduler can be hard to predict"
    When using the `DaskExecutor`, Prefect is submitting each task run to a dask cluster object.  [The dask scheduler then determines when and how each individual run should be executed](https://distributed.dask.org/en/latest/scheduling-policies.html) (with the constraint that the order matches the execution graph that Prefect provided).  

    This means that the only way to _force_ dask to walk the task graph in a particular order is to configure Prefect dependencies between your tasks.

## Asynchronous Execution

Prefect supports asynchronous task and flow definitions.  All of the standard rules of async apply:

```python
import asyncio

@task
async def print_values(values):
    for value in values:
        await asyncio.sleep(1) # yield
        print(value, end=" ")

@flow
async def async_flow():
    await print_values([1, 2]) # runs immediately
    coros = [] 
    coros.append(print_values("abcd"))
    coros.append(print_values("6789"))

    # asynchronously gather the tasks
    await asyncio.gather(*coros)
```

When we run this flow, we find that the coroutines that were gathered yield control to one another and are run concurrently:

<div class="termy">
```
>>> await async_flow()
1 2 a 6 b 7 c 8 d 9
```
</div>

Asynchronous task execution is currently supported with all executors.

!!! warning "Asynchronous tasks within synchronous flows"
    Asynchronous tasks cannot be run within synchronous flows.  Combining asynchronous tasks with synchronous flows results in:
    ```
    RuntimeError: Your task is async, but your flow is synchronous. 
    Async tasks may only be called from async flows.
    ```
