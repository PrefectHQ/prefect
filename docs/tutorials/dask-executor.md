
# Using the Dask executor

The [DaskExecutor](/api-ref/executors.md#daskexecutor) runs Prefect
tasks using [Dask's Distributed
Scheduler](https://distributed.dask.org/en/latest/). It can be used locally on
a single machine (much like the `LocalDaskExecutor` above), but is most useful
when scaling out distributed across multiple nodes.

Prefect's `DaskExecutor` has 3 operating modes:

## Using a Local Cluster

By default, when you use a `DaskExecutor` it creates a temporary local Dask
cluster.

```python
from prefect.executors import DaskExecutor

# By default this will use a temporary local Dask cluster
@flow
def my_flow(executor=DaskExecutor()):
    pass
```

The number of workers used is based on the number of cores on your machine. The
default should provide a mix of processes and threads that should work well for
most workloads. If you want to specify this explicitly, you can pass
`n_workers` or `threads_per_worker` to `cluster_kwargs`.

```python
# Use 4 worker processes, each with 2 threads
DaskExecutor(
    cluster_kwargs={"n_workers": 4, "threads_per_worker": 2}
)
```

## Using a Temporary Cluster

The `DaskExecutor` is capable of creating a temporary cluster using any of
[Dask's cluster-manager options](https://docs.dask.org/en/latest/setup.html).
This can be useful when you want each flow run to have its own Dask cluster,
allowing for adaptive scaling per-flow.

To configure, you need to provide a `cluster_class`. This can be either a
string specifying the import path to the cluster class (e.g.
`"dask_cloudprovider.aws.FargateCluster"`), the cluster class itself, or a
function for creating a custom cluster. You can also configure
`cluster_kwargs`, which takes a dictionary of keyword arguments to pass to
`cluster_class` when starting the flow run.

For example, to configure a flow to use a temporary
`dask_cloudprovider.aws.FargateCluster` with 4 workers running with an image
named `my-prefect-image`:

```python
DaskExecutor(
    cluster_class="dask_cloudprovider.aws.FargateCluster",
    cluster_kwargs={"n_workers": 4, "image": "my-prefect-image"},
)
```

## Adaptive Scaling

One nice feature of using a `DaskExecutor` is the ability to scale adaptively
to the workload. Instead of specifying `n_workers` as a fixed number, this lets
you specify a minimum and maximum number of workers to use, and the dask
cluster will scale up and down as needed.

To do this, you can pass `adapt_kwargs` to `DaskExecutor`. This takes the
following fields:

- `maximum` (`int` or `None`, optional): the maximum number of workers to scale
  to. Set to `None` for no maximum.
- `minimum` (`int` or `None`, optional): the minimum number of workers to scale
  to. Set to `None` for no minimum.

For example, here we configure a flow to run on a `FargateCluster` scaling up
to at most 10 workers.

```python
DaskExecutor(
    cluster_class="dask_cloudprovider.aws.FargateCluster",
    adapt_kwargs={"maximum": 10}
)
```

## Connecting to an Existing Cluster

Multiple Prefect flow runs can all use the same existing Dask cluster. You
might manage a single long-running Dask cluster (maybe using the [Helm
Chart](https://docs.dask.org/en/latest/setup/kubernetes-helm.html)) and
configure flows to connect to it during execution. This has a few downsides
when compared to using a temporary cluster (as described above):

- All workers in the cluster must have dependencies installed for all flows you
  intend to run. When using a temporary cluster, each workers to run the flow
  it's associated with.

- Multiple flow runs may compete for resources. Dask tries to do a good job
  sharing resources between tasks, but you may still run into issues.

That said, you may find managing a single long running cluster simpler (the
choice here is largely preferential). To configure a `DaskExecutor` to connect
to an existing cluster, pass in the address of the scheduler to the `address`
argument:

```python
# Connect to an existing cluster running at a specified address
DaskExecutor(address="tcp://...")
```