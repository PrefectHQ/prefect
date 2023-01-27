---
description: Learn how to use the Prefect Dask and Ray task runners for parallel or distributed task execution.
tags:
    - tutorial
    - tasks
    - task runners
    - flow configuration
    - parallel execution
    - distributed execution
    - Dask
    - Ray
---

# Dask and Ray task runners

Task runners provide an execution environment for tasks. In a flow decorator, you can specify a task runner to run the tasks called in that flow.

The default task runner is the [`ConcurrentTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.ConcurrentTaskRunner). 

!!! note "Use `.submit` to run your tasks asynchronously"

    To run tasks asynchronously use the `.submit` method when you call them. If you call a task as you would normally in Python code it will run synchronously, even if you are calling the task within a flow that uses the `ConcurrentTaskRunner`, `DaskTaskRunner`, or `RayTaskRunner`.

Many real-world data workflows benefit from true parallel, distributed task execution. For these use cases, the following Prefect-developed task runners for parallel task execution may be installed as [Prefect Collections](/collections/catalog/). 

- [`DaskTaskRunner`](https://prefecthq.github.io/prefect-dask/) runs tasks requiring parallel execution using [`dask.distributed`](http://distributed.dask.org/). 
- [`RayTaskRunner`](https://prefecthq.github.io/prefect-ray/) runs tasks requiring parallel execution using [Ray](https://www.ray.io/).

These task runners can spin up a local Dask cluster or Ray instance on the fly, or let you connect with a Dask or Ray environment you've set up separately. Then you can take advantage of massively parallel computing environments.

Use Dask or Ray in your flows to choose the execution environment that fits your particular needs. 

To show you how they work, let's start small.

!!! note "Remote storage"
    We recommend configuring [remote file storage](/concepts/storage/) for task execution with `DaskTaskRunner` or `RayTaskRunner`. This ensures tasks executing in Dask or Ray have access to task result storage, particularly when accessing a Dask or Ray instance outside of your execution environment.

## Configuring a task runner

You may have seen this briefly in a previous tutorial, but let's look a bit more closely at how you can configure a specific task runner for a flow.

Let's start with the [`SequentialTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.SequentialTaskRunner). This task runner runs all tasks synchronously and may be useful when used as a debugging tool in conjunction with async code.

Let's start with this simple flow. We import the `SequentialTaskRunner`, specify a `task_runner` on the flow, and call the tasks with `.submit()`.

```python hl_lines="2 12 15 16"
from prefect import flow, task
from prefect.task_runners import SequentialTaskRunner

@task
def say_hello(name):
    print(f"hello {name}")

@task
def say_goodbye(name):
    print(f"goodbye {name}")

@flow(task_runner=SequentialTaskRunner())
def greetings(names):
    for name in names:
        say_hello.submit(name)
        say_goodbye.submit(name)

greetings(["arthur", "trillian", "ford", "marvin"])
```

Save this as `sequential_flow.py` and run it in a terminal. You'll see output similar to the following:

<div class="terminal">
```bash
$ python sequential_flow.py
16:51:17.967 | INFO    | prefect.engine - Created flow run 'humongous-mink' for flow 'greetings'
16:51:17.967 | INFO    | Flow run 'humongous-mink' - Starting 'SequentialTaskRunner'; submitted tasks will be run sequentially...
16:51:18.038 | INFO    | Flow run 'humongous-mink' - Created task run 'say_hello-811087cd-0' for task 'say_hello'
16:51:18.038 | INFO    | Flow run 'humongous-mink' - Executing 'say_hello-811087cd-0' immediately...
hello arthur
16:51:18.060 | INFO    | Task run 'say_hello-811087cd-0' - Finished in state Completed()
16:51:18.107 | INFO    | Flow run 'humongous-mink' - Created task run 'say_goodbye-261e56a8-0' for task 'say_goodbye'
16:51:18.107 | INFO    | Flow run 'humongous-mink' - Executing 'say_goodbye-261e56a8-0' immediately...
goodbye arthur
16:51:18.123 | INFO    | Task run 'say_goodbye-261e56a8-0' - Finished in state Completed()
16:51:18.134 | INFO    | Flow run 'humongous-mink' - Created task run 'say_hello-811087cd-1' for task 'say_hello'
16:51:18.134 | INFO    | Flow run 'humongous-mink' - Executing 'say_hello-811087cd-1' immediately...
hello trillian
16:51:18.150 | INFO    | Task run 'say_hello-811087cd-1' - Finished in state Completed()
16:51:18.159 | INFO    | Flow run 'humongous-mink' - Created task run 'say_goodbye-261e56a8-1' for task 'say_goodbye'
16:51:18.159 | INFO    | Flow run 'humongous-mink' - Executing 'say_goodbye-261e56a8-1' immediately...
goodbye trillian
16:51:18.181 | INFO    | Task run 'say_goodbye-261e56a8-1' - Finished in state Completed()
16:51:18.190 | INFO    | Flow run 'humongous-mink' - Created task run 'say_hello-811087cd-2' for task 'say_hello'
16:51:18.190 | INFO    | Flow run 'humongous-mink' - Executing 'say_hello-811087cd-2' immediately...
hello ford
16:51:18.210 | INFO    | Task run 'say_hello-811087cd-2' - Finished in state Completed()
16:51:18.219 | INFO    | Flow run 'humongous-mink' - Created task run 'say_goodbye-261e56a8-2' for task 'say_goodbye'
16:51:18.219 | INFO    | Flow run 'humongous-mink' - Executing 'say_goodbye-261e56a8-2' immediately...
goodbye ford
16:51:18.237 | INFO    | Task run 'say_goodbye-261e56a8-2' - Finished in state Completed()
16:51:18.246 | INFO    | Flow run 'humongous-mink' - Created task run 'say_hello-811087cd-3' for task 'say_hello'
16:51:18.246 | INFO    | Flow run 'humongous-mink' - Executing 'say_hello-811087cd-3' immediately...
hello marvin
16:51:18.264 | INFO    | Task run 'say_hello-811087cd-3' - Finished in state Completed()
16:51:18.273 | INFO    | Flow run 'humongous-mink' - Created task run 'say_goodbye-261e56a8-3' for task 'say_goodbye'
16:51:18.273 | INFO    | Flow run 'humongous-mink' - Executing 'say_goodbye-261e56a8-3' immediately...
goodbye marvin
16:51:18.290 | INFO    | Task run 'say_goodbye-261e56a8-3' - Finished in state Completed()
16:51:18.321 | INFO    | Flow run 'humongous-mink' - Finished in state Completed('All states completed.')
```
</div>

If we take out the log messages and just look at the printed output of the tasks, you see they're executed in sequential order:

<div class="terminal">
``` bash
$ python sequential_flow.py
hello arthur
goodbye arthur
hello trillian
goodbye trillian
hello ford
goodbye ford
hello marvin
goodbye marvin
```
</div>

## Running parallel tasks with Dask

You could argue that this simple flow gains nothing from parallel execution, but let's roll with it so you can see just how simple it is to take advantage of the [`DaskTaskRunner`](https://prefecthq.github.io/prefect-dask/). 

To configure your flow to use the `DaskTaskRunner`:

1. Make sure the `prefect-dask` collection is installed by running `pip install prefect-dask`.
2. In your flow code, import `DaskTaskRunner` from `prefect_dask.task_runners`.
3. Assign it as the task runner when the flow is defined using the `task_runner=DaskTaskRunner` argument.
4. Use the `.submit` method when calling functions.

This is the same flow as above, with a few minor changes to use `DaskTaskRunner` where we previously configured `SequentialTaskRunner`. Install `prefect-dask`, made these changes, then save the updated code as `dask_flow.py`.

```python hl_lines="2 12 18"
from prefect import flow, task
from prefect_dask.task_runners import DaskTaskRunner

@task
def say_hello(name):
    print(f"hello {name}")

@task
def say_goodbye(name):
    print(f"goodbye {name}")

@flow(task_runner=DaskTaskRunner())
def greetings(names):
    for name in names:
        say_hello.submit(name)
        say_goodbye.submit(name)

if __name__ == "__main__":
    greetings(["arthur", "trillian", "ford", "marvin"])
```

Note that, because you're using `DaskTaskRunner` in a script, you must use `if __name__ == "__main__":` or you'll see warnings and errors. 

Now run `dask_flow.py`. If you get warning about accepting incoming network connections, that's okay. Everythign is local in this example.

<div class="terminal">
```bash
$ python dask_flow.py
19:29:03.798 | INFO    | prefect.engine - Created flow run 'fine-bison' for flow 'greetings'

19:29:03.798 | INFO    | Flow run 'fine-bison' - Using task runner 'DaskTaskRunner' 

19:29:04.080 | INFO    | prefect.task_runner.dask - Creating a new Dask cluster with `distributed.deploy.local.LocalCluster`
16:54:18.465 | INFO    | prefect.engine - Created flow run 'radical-finch' for flow 'greetings'
16:54:18.465 | INFO    | Flow run 'radical-finch' - Starting 'DaskTaskRunner'; submitted tasks will be run concurrently...
16:54:18.465 | INFO    | prefect.task_runner.dask - Creating a new Dask cluster with `distributed.deploy.local.LocalCluster`
16:54:19.811 | INFO    | prefect.task_runner.dask - The Dask dashboard is available at http://127.0.0.1:8787/status
16:54:19.881 | INFO    | Flow run 'radical-finch' - Created task run 'say_hello-811087cd-0' for task 'say_hello'
16:54:20.364 | INFO    | Flow run 'radical-finch' - Submitted task run 'say_hello-811087cd-0' for execution.
16:54:20.379 | INFO    | Flow run 'radical-finch' - Created task run 'say_goodbye-261e56a8-0' for task 'say_goodbye'
16:54:20.386 | INFO    | Flow run 'radical-finch' - Submitted task run 'say_goodbye-261e56a8-0' for execution.
16:54:20.397 | INFO    | Flow run 'radical-finch' - Created task run 'say_hello-811087cd-1' for task 'say_hello'
16:54:20.401 | INFO    | Flow run 'radical-finch' - Submitted task run 'say_hello-811087cd-1' for execution.
16:54:20.417 | INFO    | Flow run 'radical-finch' - Created task run 'say_goodbye-261e56a8-1' for task 'say_goodbye'
16:54:20.423 | INFO    | Flow run 'radical-finch' - Submitted task run 'say_goodbye-261e56a8-1' for execution.
16:54:20.443 | INFO    | Flow run 'radical-finch' - Created task run 'say_hello-811087cd-2' for task 'say_hello'
16:54:20.449 | INFO    | Flow run 'radical-finch' - Submitted task run 'say_hello-811087cd-2' for execution.
16:54:20.462 | INFO    | Flow run 'radical-finch' - Created task run 'say_goodbye-261e56a8-2' for task 'say_goodbye'
16:54:20.474 | INFO    | Flow run 'radical-finch' - Submitted task run 'say_goodbye-261e56a8-2' for execution.
16:54:20.500 | INFO    | Flow run 'radical-finch' - Created task run 'say_hello-811087cd-3' for task 'say_hello'
16:54:20.511 | INFO    | Flow run 'radical-finch' - Submitted task run 'say_hello-811087cd-3' for execution.
16:54:20.544 | INFO    | Flow run 'radical-finch' - Created task run 'say_goodbye-261e56a8-3' for task 'say_goodbye'
16:54:20.555 | INFO    | Flow run 'radical-finch' - Submitted task run 'say_goodbye-261e56a8-3' for execution.
hello arthur
goodbye ford
goodbye arthur
hello ford
goodbye marvin
goodbye trillian
hello trillian
hello marvin
```
</div>

`DaskTaskRunner` automatically creates a local Dask cluster, then starts executing all of the tasks in parallel. The results do not return in the same order as the sequential code above.

Notice what happens if you do not use the `submit` method when calling tasks:

```python
from prefect import flow, task
from prefect_dask.task_runners import DaskTaskRunner


@task
def say_hello(name):
    print(f"hello {name}")


@task
def say_goodbye(name):
    print(f"goodbye {name}")


@flow(task_runner=DaskTaskRunner())
def greetings(names):
    for name in names:
        say_hello(name)
        say_goodbye(name)


if __name__ == "__main__":
    greetings(["arthur", "trillian", "ford", "marvin"])
```

<div class="terminal">
```bash
$ python dask_flow.py

16:57:34.534 | INFO    | prefect.engine - Created flow run 'papaya-honeybee' for flow 'greetings'
16:57:34.534 | INFO    | Flow run 'papaya-honeybee' - Starting 'DaskTaskRunner'; submitted tasks will be run concurrently...
16:57:34.535 | INFO    | prefect.task_runner.dask - Creating a new Dask cluster with `distributed.deploy.local.LocalCluster`
16:57:35.715 | INFO    | prefect.task_runner.dask - The Dask dashboard is available at http://127.0.0.1:8787/status
16:57:35.787 | INFO    | Flow run 'papaya-honeybee' - Created task run 'say_hello-811087cd-0' for task 'say_hello'
16:57:35.788 | INFO    | Flow run 'papaya-honeybee' - Executing 'say_hello-811087cd-0' immediately...
hello arthur
16:57:35.810 | INFO    | Task run 'say_hello-811087cd-0' - Finished in state Completed()
16:57:35.820 | INFO    | Flow run 'papaya-honeybee' - Created task run 'say_goodbye-261e56a8-0' for task 'say_goodbye'
16:57:35.820 | INFO    | Flow run 'papaya-honeybee' - Executing 'say_goodbye-261e56a8-0' immediately...
goodbye arthur
16:57:35.840 | INFO    | Task run 'say_goodbye-261e56a8-0' - Finished in state Completed()
16:57:35.849 | INFO    | Flow run 'papaya-honeybee' - Created task run 'say_hello-811087cd-1' for task 'say_hello'
16:57:35.849 | INFO    | Flow run 'papaya-honeybee' - Executing 'say_hello-811087cd-1' immediately...
hello trillian
16:57:35.869 | INFO    | Task run 'say_hello-811087cd-1' - Finished in state Completed()
16:57:35.878 | INFO    | Flow run 'papaya-honeybee' - Created task run 'say_goodbye-261e56a8-1' for task 'say_goodbye'
16:57:35.878 | INFO    | Flow run 'papaya-honeybee' - Executing 'say_goodbye-261e56a8-1' immediately...
goodbye trillian
16:57:35.894 | INFO    | Task run 'say_goodbye-261e56a8-1' - Finished in state Completed()
16:57:35.907 | INFO    | Flow run 'papaya-honeybee' - Created task run 'say_hello-811087cd-2' for task 'say_hello'
16:57:35.907 | INFO    | Flow run 'papaya-honeybee' - Executing 'say_hello-811087cd-2' immediately...
hello ford
16:57:35.924 | INFO    | Task run 'say_hello-811087cd-2' - Finished in state Completed()
16:57:35.933 | INFO    | Flow run 'papaya-honeybee' - Created task run 'say_goodbye-261e56a8-2' for task 'say_goodbye'
16:57:35.933 | INFO    | Flow run 'papaya-honeybee' - Executing 'say_goodbye-261e56a8-2' immediately...
goodbye ford
16:57:35.951 | INFO    | Task run 'say_goodbye-261e56a8-2' - Finished in state Completed()
16:57:35.959 | INFO    | Flow run 'papaya-honeybee' - Created task run 'say_hello-811087cd-3' for task 'say_hello'
16:57:35.959 | INFO    | Flow run 'papaya-honeybee' - Executing 'say_hello-811087cd-3' immediately...
hello marvin
16:57:35.976 | INFO    | Task run 'say_hello-811087cd-3' - Finished in state Completed()
16:57:35.985 | INFO    | Flow run 'papaya-honeybee' - Created task run 'say_goodbye-261e56a8-3' for task 'say_goodbye'
16:57:35.985 | INFO    | Flow run 'papaya-honeybee' - Executing 'say_goodbye-261e56a8-3' immediately...
goodbye marvin
16:57:36.004 | INFO    | Task run 'say_goodbye-261e56a8-3' - Finished in state Completed()
16:57:36.289 | INFO    | Flow run 'papaya-honeybee' - Finished in state Completed('All states completed.')
```
</div>

The tasks are not submitted to the `DaskTaskRunner` and are run sequentially.


## Running parallel tasks with Ray

To demonstrate the ability to flexibly apply the task runner appropriate for your workflow, use the same flow as above, with a few minor changes to use the [`RayTaskRunner`](https://prefecthq.github.io/prefect-ray/) where we previously configured `DaskTaskRunner`. 

To configure your flow to use the `RayTaskRunner`:

1. Make sure the `prefect-ray` collection is installed by running `pip install prefect-ray`.
2. In your flow code, import `RayTaskRunner` from `prefect_ray.task_runners`.
3. Assign it as the task runner when the flow is defined using the `task_runner=RayTaskRunner` argument.

!!! warning "Ray environment limitations"
    While we're excited about parallel task execution via Ray to Prefect, there are some inherent limitations with Ray you should be aware of:
    
    Alpha support for Python 3.10 was added in [Ray 1.13](https://github.com/ray-project/ray/releases/tag/ray-1.13.0).

    Ray support for non-x86/64 architectures such as ARM/M1 processors with installation from `pip` alone and will be skipped during installation of Prefect. It is possible to manually install the blocking component with `conda`. See the [Ray documentation](https://docs.ray.io/en/latest/ray-overview/installation.html#m1-mac-apple-silicon-support) for instructions.

    See the [Ray installation documentation](https://docs.ray.io/en/latest/ray-overview/installation.html) for further compatibility information.

Save this code in `ray_flow.py`.

```python hl_lines="2 12"
from prefect import flow, task
from prefect_ray.task_runners import RayTaskRunner

@task
def say_hello(name):
    print(f"hello {name}")

@task
def say_goodbye(name):
    print(f"goodbye {name}")

@flow(task_runner=RayTaskRunner())
def greetings(names):
    for name in names:
        say_hello.submit(name)
        say_goodbye.submit(name)

if __name__ == "__main__":
    greetings(["arthur", "trillian", "ford", "marvin"])
```

Now run `ray_flow.py` `RayTaskRunner` automatically creates a local Ray instance, then immediately starts executing all of the tasks in parallel. If you have an existing Ray instance, you can provide the address as a parameter to run tasks in the instance. See [Running tasks on Ray](/concepts/task-runners/#running_tasks_on_ray) for details.

## Using multiple task runners

Many workflows include a variety of tasks, and not all of them benefit from parallel execution. You'll most likely want to use the Dask or Ray task runners and spin up their respective resources only for those tasks that need them.

Because task runners are specified on flows, you can assign different task runners to tasks by using [subflows](/concepts/flows/#composing-flows) to organize those tasks.

This example uses the same tasks as the previous examples, but on the parent flow `greetings()` we use the default `ConcurrentTaskRunner`. Then we call a `ray_greetings()` subflow that uses the `RayTaskRunner` to execute the same tasks in a Ray instance. 

```python
from prefect import flow, task
from prefect_ray.task_runners import RayTaskRunner

@task
def say_hello(name):
    print(f"hello {name}")

@task
def say_goodbye(name):
    print(f"goodbye {name}")

@flow(task_runner=RayTaskRunner())
def ray_greetings(names):
    for name in names:
        say_hello.submit(name)
        say_goodbye.submit(name)

@flow()
def greetings(names):
    for name in names:
        say_hello.submit(name)
        say_goodbye.submit(name)
    ray_greetings(names)

if __name__ == "__main__":
    greetings(["arthur", "trillian", "ford", "marvin"])
```

If you save this as `ray_subflow.py` and run it, you'll see that the flow `greetings` runs as you'd expect for a concurrent flow, then flow `ray-greetings` spins up a Ray instance to run the tasks again.