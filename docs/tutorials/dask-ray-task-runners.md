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

Task runners provide the execution environment for tasks, and each flow specifies a task runner to run any tasks on that flow.

The default task runner is the [`ConcurrentTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.ConcurrentTaskRunner) runs tasks concurrently, whether they are synchronous or asynchronous functions. Concurrent means that, if any tasks block on IO, they can yield to other tasks and mixed sync and async tasks can run concurrently. This is context switching rather than parallel processing &mdash; it increases the amount of work finished at a time on a given CPU.

If you need to dictate strict sequential task execution, you can use the [`SequentialTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.SequentialTaskRunner). This may be useful as a debugging tool for async code.

Many real-world data workflows benefit from true parallel, distributed task execution. For this reason, Prefect includes the [`DaskTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.DaskTaskRunner) and [`RayTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.RayTaskRunner).

- `DaskTaskRunner` runs tasks on a [`dask.distributed`](http://distributed.dask.org/) cluster. 
- `RayTaskRunner` runs tasks using [Ray](https://www.ray.io/).

These task runners can spin up a local Dask cluster or Ray instance on the fly, or let you connect with Dask or Ray environment you've set up separately, potentially taking advantage of massively parallel computing environments.

As you'll see, using Dask or Ray in your flows is straightforward, enabling you to choose the execution environment that fits your particular needs. 

To show you how it works, let's start small.

!!! note "Remote storage"
    We recommend configuring [remote storage](/concepts/storage/) for task execution with the `DaskTaskRunner` and `RayTaskRunner`. This ensures tasks executing in Dask or Ray have access to task result storage, particularly when accessing a Dask or Ray instance outside of your execution environment.

## Configuring a task runner

You may have seen this briefly in a previous tutorial, but let's look a bit more closely at how you can configure a specific task runner for a flow.

Let's start with this simple flow. We import the `SequentialTaskRunner` and specify a `task_runner` on the flow.

```python hl_lines="2 12"
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
        say_hello(name)
        say_goodbye(name)

greetings(["arthur", "trillian", "ford", "marvin"])
```

Save this as `sequential_flow.py` and run it in a terminal. You'll see output similar to the following:

<div class="termy">
```
$ python sequential_flow.py
19:06:41.449 | INFO    | prefect.engine - Created flow run 'fragrant-mouse' for flow 'greetings'
19:06:41.449 | INFO    | Flow run 'fragrant-mouse' - Using task runner 'SequentialTaskRunner'
19:06:41.524 | INFO    | Flow run 'fragrant-mouse' - Created task run 'say_hello-d71d0552-0' for task 'say_hello'
hello arthur
19:06:41.625 | INFO    | Task run 'say_hello-d71d0552-0' - Finished in state Completed(None)
19:06:41.653 | INFO    | Flow run 'fragrant-mouse' - Created task run 'say_goodbye-18d6ba96-0' for task 'say_goodbye'
goodbye arthur
19:06:41.742 | INFO    | Task run 'say_goodbye-18d6ba96-0' - Finished in state Completed(None)
19:06:41.771 | INFO    | Flow run 'fragrant-mouse' - Created task run 'say_hello-d71d0552-1' for task 'say_hello'
hello trillian
19:06:41.857 | INFO    | Task run 'say_hello-d71d0552-1' - Finished in state Completed(None)
19:06:41.886 | INFO    | Flow run 'fragrant-mouse' - Created task run 'say_goodbye-18d6ba96-1' for task 'say_goodbye'
goodbye trillian
19:06:41.975 | INFO    | Task run 'say_goodbye-18d6ba96-1' - Finished in state Completed(None)
19:06:42.004 | INFO    | Flow run 'fragrant-mouse' - Created task run 'say_hello-d71d0552-2' for task 'say_hello'
hello ford
19:06:42.091 | INFO    | Task run 'say_hello-d71d0552-2' - Finished in state Completed(None)
19:06:42.120 | INFO    | Flow run 'fragrant-mouse' - Created task run 'say_goodbye-18d6ba96-2' for task 'say_goodbye'
goodbye ford
19:06:42.208 | INFO    | Task run 'say_goodbye-18d6ba96-2' - Finished in state Completed(None)
19:06:42.235 | INFO    | Flow run 'fragrant-mouse' - Created task run 'say_hello-d71d0552-3' for task 'say_hello'
hello marvin
19:06:42.323 | INFO    | Task run 'say_hello-d71d0552-3' - Finished in state Completed(None)
19:06:42.352 | INFO    | Flow run 'fragrant-mouse' - Created task run 'say_goodbye-18d6ba96-3' for task 'say_goodbye'
goodbye marvin
19:06:42.439 | INFO    | Task run 'say_goodbye-18d6ba96-3' - Finished in state Completed(None)
19:06:42.478 | INFO    | Flow run 'fragrant-mouse' - Finished in state Completed('All states completed.')
```
</div>

If we take out the log messages and just look at the printed output of the tasks, you see they're executed in sequential order:

<div class="termy">
```
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

You could argue that this simple flow gains nothing from parallel execution, but let's roll with it so you can see just how simple it is to take advantage of the [`DaskTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.DaskTaskRunner). 

This is the same flow as above, with a few minor changes to use `DaskTaskRunner` where we previously configured `SequentialTaskRunner`. Save this as `dask_flow.py`.

```python hl_lines="2 12 18"
from prefect import flow, task
from prefect.task_runners import DaskTaskRunner

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

Note that, because you're using `DaskTaskRunner` in a script, you must use `if __name__ == "__main__":` or you'll see warnings and errors. 

Now run `dask_flow.py`. 

<div class="termy">
```
$ python dask_flow.py
19:29:03.798 | INFO    | prefect.engine - Created flow run 'fine-bison' for flow 'greetings'
19:29:03.798 | INFO    | Flow run 'fine-bison' - Using task runner 'DaskTaskRunner'
19:29:04.080 | INFO    | prefect.task_runner.dask - Creating a new Dask cluster with `distributed.deploy.local.LocalCluster`
19:29:10.141 | INFO    | prefect.task_runner.dask - The Dask dashboard is available at http://127.0.0.1:8787/status
19:29:10.263 | INFO    | Flow run 'fine-bison' - Created task run 'say_hello-d71d0552-0' for task 'say_hello'
19:29:10.506 | INFO    | Flow run 'fine-bison' - Created task run 'say_goodbye-18d6ba96-0' for task 'say_goodbye'
19:29:10.544 | INFO    | Flow run 'fine-bison' - Created task run 'say_hello-d71d0552-1' for task 'say_hello'
19:29:10.586 | INFO    | Flow run 'fine-bison' - Created task run 'say_goodbye-18d6ba96-1' for task 'say_goodbye'
19:29:10.638 | INFO    | Flow run 'fine-bison' - Created task run 'say_hello-d71d0552-2' for task 'say_hello'
19:29:10.684 | INFO    | Flow run 'fine-bison' - Created task run 'say_goodbye-18d6ba96-2' for task 'say_goodbye'
19:29:10.731 | INFO    | Flow run 'fine-bison' - Created task run 'say_hello-d71d0552-3' for task 'say_hello'
19:29:10.861 | INFO    | Flow run 'fine-bison' - Created task run 'say_goodbye-18d6ba96-3' for task 'say_goodbye'
hello ford
hello arthur
goodbye arthur
goodbye ford
19:29:11.248 | INFO    | Task run 'say_hello-d71d0552-2' - Finished in state Completed(None)
goodbye marvin
19:29:11.286 | INFO    | Task run 'say_goodbye-18d6ba96-0' - Finished in state Completed(None)
19:29:11.300 | INFO    | Task run 'say_goodbye-18d6ba96-2' - Finished in state Completed(None)
19:29:11.312 | INFO    | Task run 'say_goodbye-18d6ba96-3' - Finished in state Completed(None)
hello trillian
hello marvin
goodbye trillian
19:29:11.402 | INFO    | Task run 'say_hello-d71d0552-0' - Finished in state Completed(None)
19:29:11.413 | INFO    | Task run 'say_goodbye-18d6ba96-1' - Finished in state Completed(None)
19:29:11.429 | INFO    | Task run 'say_hello-d71d0552-1' - Finished in state Completed(None)
19:29:11.447 | INFO    | Task run 'say_hello-d71d0552-3' - Finished in state Completed(None)
19:29:11.980 | INFO    | Flow run 'fine-bison' - Finished in state Completed('All states completed.')
```
</div>

Notice that `DaskTaskRunner` automatically creates a local Dask cluster, then immediately starts executing all of the tasks in parallel. The number of workers used is based on the number of cores on your machine. 

You can specify the mix of processes and threads explicitly by passing parameters to `DaskTaskRunner`. See [Using DaskTaskRunner](/concepts/task-runners/#using-dasktaskrunner) for details.

You can also configure `DaskTaskRunner` to:

- [Use a temporary cluster](/concepts/task-runners/#using-a-temporary-cluster)
- [Connecting to an existing cluster](/concepts/task-runners/#connecting-to-an-existing-cluster)
- [Adaptively scale to the workload](/concepts/task-runners/#adaptive-scaling)
- [Use annotations such as priority or resources](/concepts/task-runners/#dask-annotations)

## Running parallel tasks with Ray

To demonstrate the ability to flexibly apply the task runner appropriate for your workflow, used the same flow as above, with a few minor changes to use [`RayTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.RayTaskRunner) where we previously configured `DaskTaskRunner`. Save this as `ray_flow.py`.

```python hl_lines="2 12"
from prefect import flow, task
from prefect.task_runners import RayTaskRunner

@task
def say_hello(name):
    print(f"hello {name}")

@task
def say_goodbye(name):
    print(f"goodbye {name}")

@flow(task_runner=RayTaskRunner())
def greetings(names):
    for name in names:
        say_hello(name)
        say_goodbye(name)

if __name__ == "__main__":
    greetings(["arthur", "trillian", "ford", "marvin"])
```

Now run `ray_flow.py`. 

<div class="termy">
```
$ python ray_flow.py
19:55:53.579 | INFO    | prefect.engine - Created flow run 'vegan-mouflon' for flow 'greetings'
19:55:53.580 | INFO    | Flow run 'vegan-mouflon' - Using task runner 'RayTaskRunner'
19:55:53.580 | INFO    | prefect.task_runner.ray - Creating a local Ray instance
2022-02-22 19:55:58,179	INFO services.py:1374 -- View the Ray dashboard at http://127.0.0.1:8265
19:56:03.471 | INFO    | prefect.task_runner.ray - Using Ray cluster with 1 nodes.
19:56:03.471 | INFO    | prefect.task_runner.ray - The Ray UI is available at 127.0.0.1:8265
19:56:03.568 | INFO    | Flow run 'vegan-mouflon' - Created task run 'say_hello-d71d0552-0' for task 'say_hello'
19:56:03.661 | INFO    | Flow run 'vegan-mouflon' - Created task run 'say_goodbye-18d6ba96-0' for task 'say_goodbye'
19:56:03.748 | INFO    | Flow run 'vegan-mouflon' - Created task run 'say_hello-d71d0552-1' for task 'say_hello'
19:56:03.985 | INFO    | Flow run 'vegan-mouflon' - Created task run 'say_goodbye-18d6ba96-1' for task 'say_goodbye'
19:56:04.118 | INFO    | Flow run 'vegan-mouflon' - Created task run 'say_hello-d71d0552-2' for task 'say_hello'
19:56:04.292 | INFO    | Flow run 'vegan-mouflon' - Created task run 'say_goodbye-18d6ba96-2' for task 'say_goodbye'
19:56:04.352 | INFO    | Flow run 'vegan-mouflon' - Created task run 'say_hello-d71d0552-3' for task 'say_hello'
19:56:04.411 | INFO    | Flow run 'vegan-mouflon' - Created task run 'say_goodbye-18d6ba96-3' for task 'say_goodbye'
(enter_task_run_engine_from_worker pid=18342) goodbye marvin
(enter_task_run_engine_from_worker pid=18342) 19:56:10.197 | INFO    | Task run 'say_goodbye-18d6ba96-3' - Finished in state Completed(None)
(enter_task_run_engine_from_worker pid=18341) goodbye trillian
(enter_task_run_engine_from_worker pid=18344) hello marvin
(enter_task_run_engine_from_worker pid=18341) 19:56:10.184 | INFO    | Task run 'say_goodbye-18d6ba96-1' - Finished in state Completed(None)
(enter_task_run_engine_from_worker pid=18340) goodbye ford
(enter_task_run_engine_from_worker pid=18340) 19:56:10.259 | INFO    | Task run 'say_goodbye-18d6ba96-2' - Finished in state Completed(None)
(enter_task_run_engine_from_worker pid=18344) 19:56:10.233 | INFO    | Task run 'say_hello-d71d0552-3' - Finished in state Completed(None)
(enter_task_run_engine_from_worker pid=18345) goodbye arthur
(enter_task_run_engine_from_worker pid=18339) 19:56:10.398 | INFO    | Task run 'say_hello-d71d0552-1' - Finished in state Completed(None)
(enter_task_run_engine_from_worker pid=18339) hello trillian
(enter_task_run_engine_from_worker pid=18345) 19:56:10.340 | INFO    | Task run 'say_goodbye-18d6ba96-0' - Finished in state Completed(None)
(enter_task_run_engine_from_worker pid=18346) hello arthur
(enter_task_run_engine_from_worker pid=18346) 19:56:10.422 | INFO    | Task run 'say_hello-d71d0552-0' - Finished in state Completed(None)
(enter_task_run_engine_from_worker pid=18343) hello ford
19:56:12.426 | INFO    | Flow run 'vegan-mouflon' - Finished in state Completed('All states completed.')
```
</div>

`RayTaskRunner` automatically creates a local Ray instance, then immediately starts executing all of the tasks in parallel. If you have an existing Ray instance, you can provide the address as a parameter to run tasks in the instance. See [Using RayTaskRunner](/concepts/task-runners/#using-raytaskrunner) for details.

## Using multiple task runners

Many workflows include a variety of tasks, and not all of them benefit from parallel execution. You'll most likely want to use the Dask or Ray task runners and spin up their respective resources only for those tasks that need them.

Because task runners are specified on flows, you can assign different task runners to tasks by using [subflows](/concepts/flows/#subflows) to organize those tasks.

This example uses the same tasks as the previous examples, but on the parent flow `greetings()` we use the default `ConcurrentTaskRunner`. Then we call a `ray_greetings()` subflow that uses the `RayTaskRunner` to execute the same tasks in a Ray instance. 

```python
from prefect import flow, task
from prefect.task_runners import RayTaskRunner

@task
def say_hello(name):
    print(f"hello {name}")

@task
def say_goodbye(name):
    print(f"goodbye {name}")

@flow(task_runner=RayTaskRunner())
def ray_greetings(names):
    for name in names:
        say_hello(name)
        say_goodbye(name)

@flow()
def greetings(names):
    for name in names:
        say_hello(name)
        say_goodbye(name)
    ray_greetings(names)

if __name__ == "__main__":
    greetings(["arthur", "trillian", "ford", "marvin"])
```

If you save this as `ray_subflow.py` and run it, you'll see that the flow `greetings` runs as you'd expect for a concurrent flow, then flow `ray-greetings` spins up a Ray instance to run the tasks again.

<div class="termy">
```
$ python ray_subflow.py
20:05:11.717 | INFO    | prefect.engine - Created flow run 'rational-lemur' for flow 'greetings'
20:05:11.718 | INFO    | Flow run 'rational-lemur' - Using task runner 'ConcurrentTaskRunner'
20:05:11.788 | INFO    | Flow run 'rational-lemur' - Created task run 'say_hello-d71d0552-0' for task 'say_hello'
20:05:11.840 | INFO    | Flow run 'rational-lemur' - Created task run 'say_goodbye-18d6ba96-0' for task 'say_goodbye'
hello arthur
20:05:11.900 | INFO    | Flow run 'rational-lemur' - Created task run 'say_hello-d71d0552-1' for task 'say_hello'
goodbye arthur
20:05:11.975 | INFO    | Flow run 'rational-lemur' - Created task run 'say_goodbye-18d6ba96-1' for task 'say_goodbye'
20:05:12.031 | INFO    | Task run 'say_hello-d71d0552-0' - Finished in state Completed(None)
goodbye trillian
20:05:12.060 | INFO    | Task run 'say_goodbye-18d6ba96-0' - Finished in state Completed(None)
20:05:12.082 | INFO    | Flow run 'rational-lemur' - Created task run 'say_hello-d71d0552-2' for task 'say_hello'
20:05:12.123 | INFO    | Task run 'say_goodbye-18d6ba96-1' - Finished in state Completed(None)
20:05:12.136 | INFO    | Flow run 'rational-lemur' - Created task run 'say_goodbye-18d6ba96-2' for task 'say_goodbye'
hello ford
20:05:12.200 | INFO    | Flow run 'rational-lemur' - Created task run 'say_hello-d71d0552-3' for task 'say_hello'
goodbye ford
20:05:12.277 | INFO    | Flow run 'rational-lemur' - Created task run 'say_goodbye-18d6ba96-3' for task 'say_goodbye'
hello marvin
goodbye marvin
20:05:12.397 | INFO    | Task run 'say_goodbye-18d6ba96-2' - Finished in state Completed(None)
20:05:12.429 | INFO    | Task run 'say_hello-d71d0552-2' - Finished in state Completed(None)
20:05:12.440 | INFO    | Task run 'say_goodbye-18d6ba96-3' - Finished in state Completed(None)
20:05:12.453 | INFO    | Task run 'say_hello-d71d0552-3' - Finished in state Completed(None)
20:05:12.477 | INFO    | Flow run 'rational-lemur' - Created subflow run 'powerful-parrot' for flow 'ray-greetings'
20:05:12.478 | INFO    | prefect.task_runner.ray - Creating a local Ray instance
2022-02-22 20:05:16,146	INFO services.py:1374 -- View the Ray dashboard at http://127.0.0.1:8265
20:05:21.214 | INFO    | prefect.task_runner.ray - Using Ray cluster with 1 nodes.
20:05:21.214 | INFO    | prefect.task_runner.ray - The Ray UI is available at 127.0.0.1:8265
hello trillian
20:05:21.326 | INFO    | Task run 'say_hello-d71d0552-1' - Finished in state Completed(None)
20:05:21.350 | INFO    | Flow run 'powerful-parrot' - Created task run 'say_hello-d71d0552-4' for task 'say_hello'
20:05:21.422 | INFO    | Flow run 'powerful-parrot' - Created task run 'say_goodbye-18d6ba96-4' for task 'say_goodbye'
20:05:21.488 | INFO    | Flow run 'powerful-parrot' - Created task run 'say_hello-d71d0552-5' for task 'say_hello'
20:05:21.539 | INFO    | Flow run 'powerful-parrot' - Created task run 'say_goodbye-18d6ba96-5' for task 'say_goodbye'
20:05:21.773 | INFO    | Flow run 'powerful-parrot' - Created task run 'say_hello-d71d0552-6' for task 'say_hello'
20:05:21.886 | INFO    | Flow run 'powerful-parrot' - Created task run 'say_goodbye-18d6ba96-6' for task 'say_goodbye'
20:05:21.996 | INFO    | Flow run 'powerful-parrot' - Created task run 'say_hello-d71d0552-7' for task 'say_hello'
20:05:22.092 | INFO    | Flow run 'powerful-parrot' - Created task run 'say_goodbye-18d6ba96-7' for task 'say_goodbye'
(enter_task_run_engine_from_worker pid=20883) hello trillian
(enter_task_run_engine_from_worker pid=20881) goodbye marvin
(enter_task_run_engine_from_worker pid=20881) 20:05:27.915 | INFO    | Task run 'say_goodbye-18d6ba96-7' - Finished in state Completed(None)
(enter_task_run_engine_from_worker pid=20887) hello arthur
(enter_task_run_engine_from_worker pid=20887) 20:05:27.927 | INFO    | Task run 'say_hello-d71d0552-4' - Finished in state Completed(None)
(enter_task_run_engine_from_worker pid=20883) 20:05:27.948 | INFO    | Task run 'say_hello-d71d0552-5' - Finished in state Completed(None)
(enter_task_run_engine_from_worker pid=20886) 20:05:28.011 | INFO    | Task run 'say_goodbye-18d6ba96-5' - Finished in state Completed(None)
(enter_task_run_engine_from_worker pid=20885) goodbye arthur
(enter_task_run_engine_from_worker pid=20885) 20:05:28.041 | INFO    | Task run 'say_goodbye-18d6ba96-4' - Finished in state Completed(None)
(enter_task_run_engine_from_worker pid=20886) goodbye trillian
(enter_task_run_engine_from_worker pid=20882) hello marvin
(enter_task_run_engine_from_worker pid=20882) 20:05:28.157 | INFO    | Task run 'say_hello-d71d0552-7' - Finished in state Completed(None)
(enter_task_run_engine_from_worker pid=20884) 20:05:28.259 | INFO    | Task run 'say_goodbye-18d6ba96-6' - Finished in state Completed(None)
(enter_task_run_engine_from_worker pid=20884) goodbye ford
20:05:30.158 | INFO    | Flow run 'powerful-parrot' - Finished in state Completed('All states completed.')
20:05:31.866 | INFO    | Flow run 'rational-lemur' - Finished in state Completed('All states completed.')
```
</div>

