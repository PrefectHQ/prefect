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
    - submit
---

# Flow and task execution

So far you've seen that flows are the fundamental component of Prefect workflows, and tasks are components that enable you to encapsulate discrete, repeatable units of work within flows. You've also seen some of the configuration options for flows and tasks.

One of the configuration options demonstrated in the [Flow and task configuration](/tutorials/flow-task-config/) tutorial was setting a task runner that enables different execution capabilities for tasks _within a single flow run_. 

## Task runners

Task runners are responsible for running Prefect tasks within a flow. Each flow has a task runner associated with it. Depending on the task runner you use, the tasks within your flow can run sequentially, concurrently, or in parallel. You can even configure task runners to use distributed execution infrastructure such as a Dask cluster.

The default task runner is the `ConcurrentTaskRunner`, which will run submitted tasks concurrently. If you don't specify a task runner, Prefect uses the `ConcurrentTaskRunner`.

All Prefect task runners support asynchronous task execution.

## Result
By default, the result of a task is a Python object, and execution of the task blocks the execution of the next task in a flow. To make sure that the tasks within your flow can run concurrently or in parallel, add `.submit()` to your task run. This method will return a `PrefectFuture` instead of a Python object.

A `PrefectFuture` is an object that provides access to a computation happening in a task runner. Here's an example of using `.submit` in a flow.

```python
import time
from prefect import task, flow

@task
def my_task():
    return 1

@flow
def my_flow():
    result = my_task.submit()

if __name__ == "__main__":
    my_flow()
```

## Concurrent execution

As mentioned, by default Prefect flows use the `ConcurrentTaskRunner` for non-blocking, concurrent execution of tasks.


Here's a basic flow and task using the default task runner.

```python
import time
from prefect import task, flow

@task
def print_values(values):
    for value in values:
        time.sleep(0.5)
        print(value, end="\r")

@flow
def my_flow():
    print_values.submit(["AAAA"] * 15)
    print_values.submit(["BBBB"] * 10)

if __name__ == "__main__":
    my_flow()
```

When you run this flow you should see the terminal output randomly switching between `AAAA` and `BBBB` showing that these two tasks are indeed not blocking.

Also notice that `Starting 'ConcurrentTaskRunner'; submitted tasks will be run concurrently...` indicates Prefect is, in fact, using concurrent execution by default for the tasks in this flow.

<div class="terminal">
```bash
15:07:10.015 | INFO    | prefect.engine - Created flow run 'mindful-tortoise' for flow 'parallel-flow'
15:07:10.015 | INFO    | Flow run 'mindful-tortoise' - Starting 'ConcurrentTaskRunner'; submitted tasks will be run concurrently...
15:07:10.255 | INFO    | Flow run 'mindful-tortoise' - Created task run 'print_values-0bb9a2c3-0' for task 'print_values'
15:07:10.255 | INFO    | Flow run 'mindful-tortoise' - Submitted task run 'print_values-0bb9a2c3-0' for execution.
15:07:10.291 | INFO    | Flow run 'mindful-tortoise' - Created task run 'print_values-0bb9a2c3-1' for task 'print_values'
15:07:10.292 | INFO    | Flow run 'mindful-tortoise' - Submitted task run 'print_values-0bb9a2c3-1' for execution.
15:07:15.364 | INFO    | Task run 'print_values-0bb9a2c3-1' - Finished in state Completed()
15:07:17.849 | INFO    | Task run 'print_values-0bb9a2c3-0' - Finished in state Completed()
15:07:17.876 | INFO    | Flow run 'mindful-tortoise' - Finished in state Completed('All states completed.')
```
</div>

## Sequential execution

Sometimes you may want to intentionally run tasks sequentially. The built-in Prefect `SequentialTaskRunner` lets you do this.

When using non-default task runner, you must import the task runner into your flow script.

```python hl_lines="3 11"
import time
from prefect import task, flow
from prefect.task_runners import SequentialTaskRunner

@task
def print_values(values):
    for value in values:
        time.sleep(0.5)
        print(value, end="\r")

@flow(task_runner=SequentialTaskRunner())
def my_flow():
    print_values.submit(["AAAA"] * 15)
    print_values.submit(["BBBB"] * 10)

if __name__ == "__main__":
    my_flow()
```

When you run this flow you should see the terminal output first display `AAAA`, then `BBBB` showing that these two task runs execute sequentially, one completing before the second starts.

Also notice that `Starting 'SequentialTaskRunner'; submitted tasks will be run sequentially...` indicates Prefect is, in fact, using sequential execution.

<div class="terminal">
```bash
15:15:28.226 | INFO    | prefect.engine - Created flow run 'thundering-camel' for flow 'my-flow'
15:15:28.227 | INFO    | Flow run 'thundering-camel' - Starting 'SequentialTaskRunner'; submitted tasks will be run sequentially...
15:15:28.460 | INFO    | Flow run 'thundering-camel' - Created task run 'print_values-0bb9a2c3-0' for task 'print_values'
15:15:28.461 | INFO    | Flow run 'thundering-camel' - Executing 'print_values-0bb9a2c3-0' immediately...
15:15:36.087 | INFO    | Task run 'print_values-0bb9a2c3-0' - Finished in state Completed()
15:15:36.110 | INFO    | Flow run 'thundering-camel' - Created task run 'print_values-0bb9a2c3-1' for task 'print_values'
15:15:36.111 | INFO    | Flow run 'thundering-camel' - Executing 'print_values-0bb9a2c3-1' immediately...
15:15:41.207 | INFO    | Task run 'print_values-0bb9a2c3-1' - Finished in state Completed()
15:15:41.237 | INFO    | Flow run 'thundering-camel' - Finished in state Completed('All states completed.')
```
</div>

## Parallel execution

You can also run tasks using parallel or distributed execution by using the Dask or Ray task runners available through [Prefect Collections](/collections/overview/). 

For example, you can achieve parallel task execution, even on in a local execution environment, but using the `DaskTaskRunner`.

1. Install the [prefect-dask collection](https://prefecthq.github.io/prefect-dask/) with `pip install prefect-dask`.
1. Switch your task runner to the `DaskTaskRunner`. 
1. Call `.submit` on the task instead of calling the task directly. This submits the task to the task runner rather than running the task in-process.

<!-- To do: add brief explanation of `.submit()` -->

```python
import time
from prefect import task, flow
from prefect_dask.task_runners import DaskTaskRunner

@task
def print_values(values):
    for value in values:
        time.sleep(0.5)
        print(value, end="\r")

@flow(task_runner=DaskTaskRunner())
def my_flow():
    print_values.submit(["AAAA"] * 15)
    print_values.submit(["BBBB"] * 10)

if __name__ == "__main__":
    my_flow()
```

!!! tip "Multiprocessing task runners"
    Because the `DaskTaskRunner` uses multiprocessing, it must be protected by an `if __name__ == "__main__":` guard when used in a script.

When you run this flow you should see the terminal output randomly switching between `AAAA` and `BBBB` showing that these two tasks are indeed running in parallel.

If you have the [bokeh](https://docs.bokeh.org/en/latest/) Python package installed you can follow the link to the Dask dashaboard in the terminal output and watch the Dask workers in action!

<div class="terminal">
```bash
22:49:06.969 | INFO    | prefect.engine - Created flow run 'bulky-unicorn' for flow 'parallel-flow'
22:49:06.969 | INFO    | Flow run 'bulky-unicorn' - Using task runner 'DaskTaskRunner'
22:49:06.970 | INFO    | prefect.task_runner.dask - Creating a new Dask cluster with `distributed.deploy.local.LocalCluster`
22:49:09.182 | INFO    | prefect.task_runner.dask - The Dask dashboard is available at http://127.0.0.1:8787/status
...
```
</div>

!!! warning "The Dask scheduler can be hard to predict"
    When using the `DaskTaskRunner`, Prefect is submitting each task run to a Dask cluster object.  The Dask scheduler then [determines when and how each individual run should be executed](https://distributed.dask.org/en/latest/scheduling-policies.html) (with the constraint that the order matches the execution graph that Prefect provided).  

    This means the only way to _force_ Dask to walk the task graph in a particular order is to configure Prefect dependencies between your tasks.

Read more about using Dask in the [Dask task runner tutorial](/tutorials/dask-ray-task-runners/#running-parallel-tasks-with-dask).

## Asynchronous execution

Prefect also supports asynchronous task and flow definitions by default. All of [the standard rules of async](https://docs.python.org/3/library/asyncio-task.html) apply:

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

asyncio.run(async_flow())
```

When you run this flow, the coroutines that were gathered yield control to one another and are run concurrently:

<div class="terminal">
```bash
1 2 a 6 b 7 c 8 d 9
```
</div>

The example above is equivalent to below:

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
    await print_values.submit("abcd")
    await print_values.submit("6789")

asyncio.run(async_flow())
```

Note, if you are not using `asyncio.gather`, calling `submit` is required for asynchronous execution on the `ConcurrentTaskRunner`.

## Flow execution

Task runners only manage _task runs_ within a flow run. But what about flows?

Any given flow run &mdash; meaning in this case your workflow including any subflows and tasks &mdash; executes in its own environment using the infrastructure configured for that environment. In these examples, that infrastructure is probably your local computing environment. But for flow runs based on [deployments](/concepts/deployments/), that infrastructure might be a server in a datacenter, a VM, a Docker container, or a Kubernetes cluster.

The ability to execute flow runs in a non-blocking or parallel manner is subject to execution infrastructure and the configuration of [agents and work queues](/concepts/work-queues/) &mdash; advanced topics that are covered in other tutorials.

Within a flow, subflow runs behave like normal flow runs, except subflows will block execution of the parent flow until completion. However, asynchronous subflows are supported using AnyIO task groups or `asyncio.gather`.

!!! tip "Next steps: Flow orchestration with Prefect"
    The next step is learning about [the components of Prefect](/tutorials/orion/) that enable coordination and orchestration of your flow and task runs.
