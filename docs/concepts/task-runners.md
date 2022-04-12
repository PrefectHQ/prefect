---
description: Task runners enable sequential, concurrent, parallel, or distributed execution of Prefect tasks.
tags:
    - Orion
    - tasks
    - task runners
    - concurrent execution
    - sequential execution
    - parallel execution
    - Dask
    - Ray
---

# Task runners

Task runners are responsible for running Prefect tasks. Each flow has a task runner associated with it. The task runner is started at the beginning of a flow run and shutdown at the end.

Depending on the task runner you use, the tasks within your flow can run sequentially, concurrently, or in parallel. The default task runner is the [`ConcurrentTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.ConcurrentTaskRunner), which will run your tasks concurrently. 

Prefect currently provides the following task runners: 

- [`ConcurrentTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.ConcurrentTaskRunner) runs tasks concurrently.
- [`SequentialTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.SequentialTaskRunner) runs tasks sequentially. 
- [`DaskTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.DaskTaskRunner) runs tasks requiring parallel execution using [`dask.distributed`](http://distributed.dask.org/). 
- [`RayTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.RayTaskRunner) runs tasks requiring parallel execution using [Ray](https://www.ray.io/).

## Using a task runner

While all flows require a task runner to execute tasks, you do not need to specify a task runner unless your tasks require specific execution. If you do not specify a task runner, Prefect uses the default `ConcurrentTaskRunner`.

To configure your flow to use a specific task runner, import task runners from [`prefect.task_runners`](/api-ref/prefect/task-runners/) and assign them when the flow is defined.

```python hl_lines="2 4"
from prefect import flow
from prefect.task_runners import SequentialTaskRunner

@flow(task_runner=SequentialTaskRunner())
def my_flow():
    pass
```

If you specify an uninitialized task runner class, a task runner instance of that type is created with the default settings. You can also pass additional configuration parameters for task runners that accept parameters, such as [`DaskTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.DaskTaskRunner) and [`RayTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.RayTaskRunner).

## Running tasks on Dask

The [`DaskTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.DaskTaskRunner) is a parallel task runner that submits tasks to the [`dask.distributed`](http://distributed.dask.org/) scheduler. By default, a temporary Dask cluster is created for the duration of the flow run. If you already have a Dask cluster running, either local or cloud hosted, you can provide the connection URL via the `address` kwarg.

To configure your flow to use the `DaskTaskRunner`, import it from [`prefect.task_runners`](/api-ref/prefect/task-runners/) and assign it as the task runner when the flow is defined.

```python hl_lines="4"
from prefect import flow
from prefect.task_runner import DaskTaskRunner

@flow(task_runner=DaskTaskRunner(address="http://my-dask-cluster"))
def my_flow():
    pass
```

`DaskTaskRunner` accepts the following optional parameters:

| Parameter | Description |
| --- | --- |
| address | Address of a currently running Dask scheduler. |
| cluster_class | The cluster class to use when creating a temporary Dask cluster. It can be either the full class name (for example, `"distributed.LocalCluster"`), or the class itself. |
| cluster_kwargs | Additional kwargs to pass to the `cluster_class` when creating a temporary Dask cluster. |
| adapt_kwargs | Additional kwargs to pass to `cluster.adapt` when creating a temporary Dask cluster. Note that adaptive scaling is only enabled if `adapt_kwargs` are provided. |
| client_kwargs | Additional kwargs to use when creating a [`dask.distributed.Client`](https://distributed.dask.org/en/latest/api.html#client). |

!!! warning "Multiprocessing safety"
    Note that, because the `DaskTaskRunner` uses multiprocessing, calls to flows
    in scripts must be guarded with `if __name__ == "__main__":` or you will encounter 
    warnings and errors.

If you don't provide the `address` of a Dask scheduler, a temporary local cluster will be created automatically.
The number of workers used is based on the number of cores on your machine. The
default should provide a mix of processes and threads that should work well for
most workloads. If you want to specify this explicitly, you can pass
`n_workers` or `threads_per_worker` to `cluster_kwargs`.

```python
# Use 4 worker processes, each with 2 threads
DaskTaskRunner(
    cluster_kwargs={"n_workers": 4, "threads_per_worker": 2}
)
```

### Using a temporary cluster

The `DaskTaskRunner` is capable of creating a temporary cluster using any of
[Dask's cluster-manager options](https://docs.dask.org/en/latest/setup.html).
This can be useful when you want each flow run to have its own Dask cluster,
allowing for adaptive scaling per-flow.

To configure, you need to provide a `cluster_class`. This can be either a
string specifying the import path to the cluster class (for example,
`"dask_cloudprovider.aws.FargateCluster"`), the cluster class itself, or a
function for creating a custom cluster. You can also configure
`cluster_kwargs`, which takes a dictionary of keyword arguments to pass to
`cluster_class` when starting the flow run.

For example, to configure a flow to use a temporary
`dask_cloudprovider.aws.FargateCluster` with 4 workers running with an image
named `my-prefect-image`:

```python
DaskTaskRunner(
    cluster_class="dask_cloudprovider.aws.FargateCluster",
    cluster_kwargs={"n_workers": 4, "image": "my-prefect-image"},
)
```

### Connecting to an existing cluster

Multiple Prefect flow runs can all use the same existing Dask cluster. You
might manage a single long-running Dask cluster (maybe using the Dask 
[Helm Chart](https://docs.dask.org/en/latest/setup/kubernetes-helm.html)) and
configure flows to connect to it during execution. This has a few downsides
when compared to using a temporary cluster (as described above):

- All workers in the cluster must have dependencies installed for all flows you
  intend to run.
- Multiple flow runs may compete for resources. Dask tries to do a good job
  sharing resources between tasks, but you may still run into issues.

That said, you may prefer managing a single long running cluster. 

To configure a `DaskTaskRunner` to connect to an existing cluster, pass in the address of the
scheduler to the `address` argument:

```python
# Connect to an existing cluster running at a specified address
DaskTaskRunner(address="tcp://...")
```

### Adaptive scaling

One nice feature of using a `DaskTaskRunner` is the ability to scale adaptively
to the workload. Instead of specifying `n_workers` as a fixed number, this lets
you specify a minimum and maximum number of workers to use, and the dask
cluster will scale up and down as needed.

To do this, you can pass `adapt_kwargs` to `DaskTaskRunner`. This takes the
following fields:

- `maximum` (`int` or `None`, optional): the maximum number of workers to scale
  to. Set to `None` for no maximum.
- `minimum` (`int` or `None`, optional): the minimum number of workers to scale
  to. Set to `None` for no minimum.

For example, here we configure a flow to run on a `FargateCluster` scaling up
to at most 10 workers.

```python
DaskTaskRunner(
    cluster_class="dask_cloudprovider.aws.FargateCluster",
    adapt_kwargs={"maximum": 10}
)
```

### Dask annotations

Dask annotations can be used to further control the behavior of tasks.

For example, we can set the [priority](http://distributed.dask.org/en/stable/priority.html) of tasks in the Dask scheduler:

```python
import dask
from prefect import flow, task
from prefect.task_runners import DaskTaskRunner

@task
def show(x):
    print(x)


@flow(task_runner=DaskTaskRunner())
def my_flow():
    with dask.annotate(priority=-10):
        future = show(1)  # low priority task

    with dask.annotate(priority=10):
        future = show(2)  # high priority task
```

Another common use case is [resource](http://distributed.dask.org/en/stable/resources.html) annotations:

```python
import dask
from prefect import flow, task
from prefect.task_runners import DaskTaskRunner

@task
def show(x):
    print(x)

# Create a `LocalCluster` with some resource annotations
# Annotations are abstract in dask and not inferred from your system.
# Here, we claim that our system has 1 GPU and 1 process available per worker
@flow(
    task_runner=DaskTaskRunner(
        cluster_kwargs={"n_workers": 1, "resources": {"GPU": 1, "process": 1}}
    )
)
def my_flow():
    with dask.annotate(resources={'GPU': 1}):
        future = show(0)  # this task requires 1 GPU resource on a worker

    with dask.annotate(resources={'process': 1}):
        # These tasks each require 1 process on a worker; because we've 
        # specified that our cluster has 1 process per worker and 1 worker,
        # these tasks will run sequentially
        future = show(1)
        future = show(2)
        future = show(3)
```

## Running tasks on Ray

The [`RayTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.RayTaskRunner) is a parallel task runner that submits tasks to [Ray](https://www.ray.io/). By default, a temporary Ray instance is created for the duration of the flow run. If you already have a Ray instance running, you can provide the connection URL via the `address` kwarg.

```python hl_lines="4"
from prefect import flow
from prefect.task_runners import RayTaskRunner

@flow(task_runner=RayTaskRunner(address="ray://192.0.2.255:8786"))
def my_flow():
    pass 
```

`RayTaskRunner` accepts the following optional parameters:

| Parameter | Description |
| --- | --- |
| address | Address of a currently running Ray instance, starting with the [ray://](https://docs.ray.io/en/master/cluster/ray-client.html) URI. |
| init_kwargs | Additional kwargs to use when calling `ray.init`. |

Note that Ray Client uses the [ray://](https://docs.ray.io/en/master/cluster/ray-client.html) URI to indicate the address of a Ray instance. If you don't provide the `address` of a Ray instance, a temporary instance will be created automatically.

!!! warning "Ray environment limitations"
    While we're excited about adding support for parallel task execution via Ray to Prefect, there are some inherent limitations with Ray you should be aware of:
    
    Ray currently does not support Python 3.10.

## Running tasks sequentially

Sometimes, it's useful to force tasks to run sequentially to make it easier to reason about the behavior of your program. Switching to the `SequentialTaskRunner` will force both sync and async tasks to run sequentially rather than concurrently.

The following example somewhat trivializes the issue, but demonstrates using the `SequentialTaskRunner` to ensure sequential task execution (the elevator stops on each floor in order):

```python
from prefect import flow, task
from prefect.task_runners import SequentialTaskRunner
import random

@task
def stop_at_floor(floor):
    situation = random.choice(["on fire","clear"])
    print(f"elevator stops on {floor} which is {situation}")

@flow(task_runner=SequentialTaskRunner(),
      name="towering-infernflow",
      )
def glass_tower():
    for floor in range(1,39):
        stop_at_floor(floor)
    
glass_tower()
```

## Using multiple task runners

Each flow can only have a single task runner, but sometimes you may want a subset of your tasks to run using a specific task runner. In this case, you can create [subflows](/concepts/flows/#subflows) for tasks that need to use a different task runner.

For example, you can have a flow (`sequential_flow`) that runs its tasks locally using the `SequentialTaskRunner`. If you have some tasks that can run more efficiently in parallel on a Dask cluster, you could create a subflow (`dask_subflow`) to run those tasks using the `DaskTaskRunner`.

```python
from prefect import flow, task
from prefect.task_runners import DaskTaskRunner, SequentialTaskRunner

@task
def hello_local():
    print("Hello!")

@task
def hello_dask():
    print("Hello from Dask!")

@flow(task_runner=SequentialTaskRunner())
def sequential_flow():
    hello_local()
    dask_subflow()
    hello_local()

@flow(task_runner=DaskTaskRunner())
def dask_subflow():
    hello_dask()

sequential_flow()
```

This script outputs the following logs demonstrating the temporary Dask task runner:

<div class="termy">
```
13:46:58.865 | Beginning flow run 'olivine-swan' for flow 'sequential-flow'...
13:46:58.866 | Starting task runner `SequentialTaskRunner`...
13:46:58.934 | Submitting task run 'hello_local-a087a829-0' to task runner...
Hello!
13:46:58.955 | Task run 'hello_local-a087a829-0' finished in state Completed(message=None, type=COMPLETED)
13:46:58.981 | Beginning subflow run 'discreet-peacock' for flow 'dask-subflow'...
13:46:58.981 | Starting task runner `DaskTaskRunner`...
13:46:58.981 | Creating a new Dask cluster with `distributed.deploy.local.LocalCluster`
13:46:59.339 | The Dask dashboard is available at http://127.0.0.1:8787/status
13:46:59.369 | Submitting task run 'hello_dask-e80d21db-0' to task runner...
Hello from Dask!
13:47:00.066 | Task run 'hello_dask-e80d21db-0' finished in state Completed(message=None, type=COMPLETED)
13:47:00.070 | Shutting down task runner `DaskTaskRunner`...
13:47:00.294 | Subflow run 'discreet-peacock' finished in state Completed(message='All states completed.', type=COMPLETED)
13:47:00.305 | Submitting task run 'hello_local-a087a829-1' to task runner...
Hello!
13:47:00.325 | Task run 'hello_local-a087a829-1' finished in state Completed(message=None, type=COMPLETED)
13:47:00.326 | Shutting down task runner `SequentialTaskRunner`...
13:47:00.334 | Flow run 'olivine-swan' finished in state Completed(message='All states completed.', type=COMPLETED)
```
</div>

