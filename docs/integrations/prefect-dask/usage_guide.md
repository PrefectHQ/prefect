# Usage Guide

Use `prefect-dask` to speed up code with parallelization.

## Run tasks on Dask

The `DaskTaskRunner` is a parallel task runner that submits tasks to the [`dask.distributed`](http://distributed.dask.org/) scheduler.

By default, a temporary Dask cluster is created for the duration of the flow run.

For example, this flow counts up to 10 in parallel (note that the output is not sequential).

```python
import time

from prefect import flow, task
from prefect_dask import DaskTaskRunner

@task
def shout(number):
    time.sleep(0.5)
    print(f"#{number}")

@flow(task_runner=DaskTaskRunner)
def count_to(highest_number):
    for number in range(highest_number):
        shout.submit(number)

if __name__ == "__main__":
    count_to(10)

# outputs
#3
#7
#2
#6
#4
#0
#1
#5
#8
#9
```

If you already have a Dask cluster running, either local or cloud hosted, you can provide the connection URL via an `address` argument.

To configure your flow to use the `DaskTaskRunner`:

1. Make sure the `prefect-dask` collection is installed as described earlier: `pip install prefect-dask`.
2. In your flow code, import `DaskTaskRunner` from `prefect_dask.task_runners`.
3. Assign it as the task runner when the flow is defined using the `task_runner=DaskTaskRunner` argument.

For example, this flow uses the `DaskTaskRunner` configured to access an existing Dask cluster at `http://my-dask-cluster`.

```python
from prefect import flow
from prefect_dask.task_runners import DaskTaskRunner

@flow(task_runner=DaskTaskRunner(address="http://my-dask-cluster"))
def my_flow():
    ...
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

If you don't provide the `address` of a Dask scheduler, Prefect creates a temporary local cluster automatically. The number of workers used is based on the number of cores available to your execution environment. The default provides a mix of processes and threads that should work well for most workloads. If you want to specify this explicitly, you can pass values for `n_workers` or `threads_per_worker` to `cluster_kwargs`.

```python
# Use 4 worker processes, each with 2 threads
DaskTaskRunner(
    cluster_kwargs={"n_workers": 4, "threads_per_worker": 2}
)
```

## Distributing Dask collections across workers

If you use a Dask collection, such as a `dask.DataFrame` or `dask.Bag`, to distribute the work across workers and achieve parallel computations, use one of the context managers `get_dask_client` or `get_async_dask_client`:

```python
import dask
from prefect import flow, task
from prefect_dask import DaskTaskRunner, get_dask_client

@task
def compute_task():
    with get_dask_client() as client:
        df = dask.datasets.timeseries("2000", "2001", partition_freq="4w")
        summary_df = df.describe().compute()
    return summary_df

@flow(task_runner=DaskTaskRunner())
def dask_flow():
    prefect_future = compute_task.submit()
    return prefect_future.result()

dask_flow()
```

The context managers can be used the same way in both `flow` run contexts and `task` run contexts.

!!! warning "Resolving futures in sync client"
    Note, by default, `dask_collection.compute()` returns concrete values while `client.compute(dask_collection)` returns Dask Futures. Therefore, if you call `client.compute`, you must resolve all futures before exiting out of the context manager by either:

    1. setting `sync=True`
    ```python
    with get_dask_client() as client:
        df = dask.datasets.timeseries("2000", "2001", partition_freq="4w")
        summary_df = client.compute(df.describe(), sync=True)
    ```

    2. calling `result()`
    ```python
    with get_dask_client() as client:
        df = dask.datasets.timeseries("2000", "2001", partition_freq="4w")
        summary_df = client.compute(df.describe()).result()
    ```
    For more information, visit the docs on [Waiting on Futures](https://docs.dask.org/en/stable/futures.html#waiting-on-futures).

There is also an equivalent context manager for asynchronous tasks and flows: `get_async_dask_client`.

```python
import asyncio

import dask
from prefect import flow, task
from prefect_dask import DaskTaskRunner, get_async_dask_client

@task
async def compute_task():
    async with get_async_dask_client() as client:
        df = dask.datasets.timeseries("2000", "2001", partition_freq="4w")
        summary_df = await client.compute(df.describe())
    return summary_df

@flow(task_runner=DaskTaskRunner())
async def dask_flow():
    prefect_future = await compute_task.submit()
    return await prefect_future.result()

asyncio.run(dask_flow())
```

!!! warning "Resolving futures in async client"
    With the async client, you do not need to set `sync=True` or call `result()`.

    However, you must `await client.compute(dask_collection)` before exiting the context manager.

    To invoke `compute` from the Dask collection, set `sync=False` and call `result()` before exiting out of the context manager: `await dask_collection.compute(sync=False)`.

## Use a temporary cluster

The `DaskTaskRunner` is capable of creating a temporary cluster using any of [Dask's cluster-manager options](https://docs.dask.org/en/latest/setup.html). This can be useful when you want each flow run to have its own Dask cluster, allowing for per-flow adaptive scaling.

To configure, you need to provide a `cluster_class`. This can be:

- A string specifying the import path to the cluster class (for example, `"dask_cloudprovider.aws.FargateCluster"`)
- The cluster class itself
- A function for creating a custom cluster

You can also configure `cluster_kwargs`, which takes a dictionary of keyword arguments to pass to `cluster_class` when starting the flow run.

For example, to configure a flow to use a temporary `dask_cloudprovider.aws.FargateCluster` with 4 workers running with an image named `my-prefect-image`:

```python
DaskTaskRunner(
    cluster_class="dask_cloudprovider.aws.FargateCluster",
    cluster_kwargs={"n_workers": 4, "image": "my-prefect-image"},
)
```

## Connect to an existing cluster

Multiple Prefect flow runs can all use the same existing Dask cluster. You might manage a single long-running Dask cluster (maybe using the Dask [Helm Chart](https://docs.dask.org/en/latest/setup/kubernetes-helm.html)) and configure flows to connect to it during execution. This has a few downsides when compared to using a temporary cluster (as described above):

- All workers in the cluster must have dependencies installed for all flows you intend to run.
- Multiple flow runs may compete for resources. Dask tries to do a good job sharing resources between tasks, but you may still run into issues.

That said, you may prefer managing a single long-running cluster.

To configure a `DaskTaskRunner` to connect to an existing cluster, pass in the address of the scheduler to the `address` argument:

```python
# Connect to an existing cluster running at a specified address
DaskTaskRunner(address="tcp://...")
```

## Adaptive scaling

One nice feature of using a `DaskTaskRunner` is the ability to scale adaptively to the workload. Instead of specifying `n_workers` as a fixed number, this lets you specify a minimum and maximum number of workers to use, and the dask cluster will scale up and down as needed.

To do this, you can pass `adapt_kwargs` to `DaskTaskRunner`. This takes the following fields:

- `maximum` (`int` or `None`, optional): the maximum number of workers to scale to. Set to `None` for no maximum.
- `minimum` (`int` or `None`, optional): the minimum number of workers to scale to. Set to `None` for no minimum.

For example, here we configure a flow to run on a `FargateCluster` scaling up to at most 10 workers.

```python
DaskTaskRunner(
    cluster_class="dask_cloudprovider.aws.FargateCluster",
    adapt_kwargs={"maximum": 10}
)
```

## Dask annotations

Dask annotations can be used to further control the behavior of tasks.

For example, we can set the [priority](http://distributed.dask.org/en/stable/priority.html) of tasks in the Dask scheduler:

```python
import dask
from prefect import flow, task
from prefect_dask.task_runners import DaskTaskRunner

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
from prefect_dask.task_runners import DaskTaskRunner

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
