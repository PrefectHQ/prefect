# Executors

A flow's `Executor` is responsible for running tasks in a flow. During
execution of a flow run, a flow's executor will be initialized, used to execute
all tasks in the flow, then shutdown.

To configure an executor on a flow, you can specify it as part of the
constructor, or set it as the `executor` attribute later before calling
`flow.register`. For example, to configure a flow to use a `LocalDaskExecutor`:

```python
from prefect import Flow
from prefect.executors import LocalDaskExecutor

# Set executor as part of the constructor
with Flow("example", executor=LocalDaskExecutor()) as flow:
    ...

# OR set executor as an attribute later
with Flow("example") as flow:
    ...

flow.executor = LocalDaskExecutor()
```

## Choosing an Executor

Prefect's different executors have different performance (and complexity)
characteristics. Choosing a good configuration can greatly improve your flow's
performance. Here's some general recommendations:

- If your flow already runs "fast enough", or doesn't have opportunities for
  parallelism (e.g. mapped tasks) you should use the
  [LocalExecutor](#localexecutor). It's the simplest option, and will be the
  easiest to manage.

- If your flow doesn't require excessive memory or CPU and is fine running on a
  single node, you should use the [LocalDaskExecutor](#localdaskexecutor). It's
  still pretty lightweight, but lets tasks run in parallel as local threads or
  processes.

- If your flow could benefit from levels parallelism not available on a single
  node, or requires more memory than is practical for a single process, you
  should use the [DaskExecutor](#daskexecutor). This lets you distribute your
  tasks among multiple nodes across a cluster, and can achieve high levels of
  parallelism. We recommend [using a temporary
  cluster](#using-a-temporary-cluster) when possible, but also support
  [connecting to an existing cluster](#connecting-to-an-existing-cluster).


## LocalExecutor

The [LocalExecutor](/api/latest/executors.md#localexecutor) executes all tasks
locally in a single thread. It's the default executor in Prefect. It's a good
option for quick running flows, or ones that don't expose lots of opportunities
for parallelism.

No extra configuration is required to specify the `LocalExecutor`, as it's the
default option. If needed though, you can still specify it explicitly:

```python
from prefect.executors import LocalExecutor

flow.executor = LocalExecutor()
```

## LocalDaskExecutor

The [LocalDaskExecutor](/api/latest/executors.md#localdaskexecutor) is a
good option or flows that could benefit from parallel execution, but are still
fine running on a single machine (not distributed). It can run tasks in
parallel using either threads (default) or local processes using one of [Dask's
local schedulers](https://docs.dask.org/en/latest/scheduling.html).

```python
from prefect.executors import LocalDaskExecutor

# Uses the default scheduler (threads)
flow.executor = LocalDaskExecutor()
```

To use multiple processes instead, you can pass in `scheduler="processes"`.

```python
# Use the multiprocessing scheduler
flow.executor = LocalDaskExecutor(scheduler="processes")
```

By default the number of threads or processes used is equal to the number of
cores available. This can be set explicitly by passing in `num_workers`.

```python
# Use 8 threads
flow.executor = LocalDaskExecutor(scheduler="threads", num_workers=8)

# Use 8 processes
flow.executor = LocalDaskExecutor(scheduler="processes", num_workers=8)
```

!!! tip Selecting a `scheduler` and `num_workers`
    You should use `scheduler="threads"` if:

    - Your tasks are often IO bound (e.g. API requests, uploading/downloading data,
      database calls, etc...). Tasks like these can sometimes benefit from having
      more threads than cores, but usually not more than by a factor of 2-4 (e.g.
      if you have 4 cores available, set `num_workers=16` at most).

    - Your tasks make use of separate processes (e.g.
      [ShellTask](/api/latest/tasks/shell.md)).

    - Your tasks make use of libraries like `numpy`, `pandas`, or `scikit-learn`
      that release the [global interpreter lock
      (GIL)](https://wiki.python.org/moin/GlobalInterpreterLock). The default
      value for `num_workers` is likely sufficient - tasks like these are CPU
      bound and won't benefit from multiple threads per core.

    You should use `scheduler="processes"` in most other cases. These tasks are
    also usually CPU bound, so the default value of `num_workers` should be
    sufficient.


## DaskExecutor

The [DaskExecutor](/api/latest/executors.md#daskexecutor) runs Prefect
tasks using [Dask's Distributed
Scheduler](https://distributed.dask.org/en/latest/). It can be used locally on
a single machine (much like the `LocalDaskExecutor` above), but is most useful
when scaling out distributed across multiple nodes.

Prefect's `DaskExecutor` has 3 operating modes:

### Using a Local Cluster

By default, when you use a `DaskExecutor` it creates a temporary local Dask
cluster.

```python
from prefect.executors import DaskExecutor

# By default this will use a temporary local Dask cluster
flow.executor = DaskExecutor()
```

The number of workers used is based on the number of cores on your machine. The
default should provide a mix of processes and threads that should work well for
most workloads. If you want to specify this explicitly, you can pass
`n_workers` or `threads_per_worker` to `cluster_kwargs`.

```python
# Use 4 worker processes, each with 2 threads
flow.executor = DaskExecutor(
    cluster_kwargs={"n_workers": 4, "threads_per_worker": 2}
)
```

Using a `DaskExecutor` with a local cluster is very similar to using a
`LocalDaskExecutor` with `processes=True`. You may find it more performant in
certain situations (this scheduler does a better job about managing memory),
but generally they should perform equivalently for most Prefect workflows. The
`DaskExecutor` becomes much more useful when used in a distributed context.

### Using a Temporary Cluster

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
flow.executor = DaskExecutor(
    cluster_class="dask_cloudprovider.aws.FargateCluster",
    cluster_kwargs={"n_workers": 4, "image": "my-prefect-image"},
)
```

#### Specifying Worker Images

Several Dask cluster managers run using images. It's important that the images
the dask workers are using have all the Python libraries that are required to
run your flow. You have a few options here:

- Build a static image that has everything required, and specify the image name
  explicitly in `cluster_kwargs`. All Prefect flow's running on dask will need
  at least `prefect`, `dask`, and `distributed` installed - depending on your
  flow you may have additional dependencies.

- If your flow is running on an agent that also uses images (e.g. Kubernetes,
  Docker, ECS, ...), you can also access the main image used for your Flow Run
  at runtime at `prefect.context.image`. Note that you *can't* put this
  directly into `cluster_kwargs` (since that will resolve at *registration*
  time not *run* time) - instead you'll need to define a custom function for
  creating your cluster. For example:

  ```python
  import prefect
  from dask_cloudprovider.aws import FargateCluster

  def fargate_cluster(n_workers=4):
      """Start a fargate cluster using the same image as the flow run"""
      return FargateCluster(n_workers=n_workers, image=prefect.context.image)

  flow.executor = DaskExecutor(
      cluster_class=fargate_cluster,
      cluster_kwargs={"n_workers": 4}
  )
  ```

For more information on Prefect and Docker images, see [here](./docker.md).

#### Adaptive Scaling

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
flow.executor = DaskExecutor(
    cluster_class="dask_cloudprovider.aws.FargateCluster",
    adapt_kwargs={"maximum": 10}
)
```

### Connecting to an Existing Cluster

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

- When cancelling a flow run, any actively running tasks can't be hard-stopped
  when using a shared Dask cluster - instead the flow runner will stop
  submitting tasks but will let all active tasks run to completion. With a
  temporary cluster the cluster can be shutdown to force-stop any active tasks,
  speeding up cancellation.

That said, you may find managing a single long running cluster simpler (the
choice here is largely preferential). To configure a `DaskExecutor` to connect
to an existing cluster, pass in the address of the scheduler to the `address`
argument:

```python
# Connect to an existing cluster running at a specified address
flow.executor = DaskExecutor(address="tcp://...")
```

### Performance Reports

To generate a [performance report](https://distributed.dask.org/en/latest/api.html#distributed.performance_report)
for a flow run, specify a `performance_report_path` for the `DaskExecutor`.
#### Saving the report to a local file

The performance report will saved as a `.html` file where the flow run is executed based on the `performance_report_path`.
To view the report, open the html file in a web browser.

For local execution or flows executed using a Local Agent, the file will be accessible on your local machine.

```python
# performance_report_flow.py
import os
from prefect.executors import DaskExecutor
from prefect import Flow, task

# define a simple task and flow
@task
def hello():
  return "hi"

with Flow('performance_report') as flow:
  x = hello()

# specify where the executor should write the performance report
flow.executor = DaskExecutor(performance_report_path="/path/to/performance_report.html")
```

To execute the flow and generate the performance report

```bash
prefect run -p performance_report_flow.py 
```

The performance report will be available at `/path/to/performance_report.html`.
To view the report, open the html file in a web browser.

#### Saving the report using custom logic

For other agent types, the report file location is not guaranteed to be easily accessible after execution.
When using a Kubernetes Agent, for example, the report will be saved on the Kubernetes pod responsible for
executing the flow run. (A persistent volume would need to be specified to access the report after the pod is shutdown.)

For cases in which the performance report location is not easily accessible after flow execution, the report 
is also available as a string in the flow's terminal state handler, which can be used to write the report to a convenient location
by accessing `flow.executor.performance_report`.

```python
# performance_report_flow.py
import io
import os
from prefect.executors import DaskExecutor
from prefect import Flow, task
from prefect.engine.state import State
from prefect.utilities.aws import get_boto_client
from typing import Set, Optional

def custom_terminal_state_handler(
	flow: Flow,
	state: State,
	reference_task_states: Set[State],
) -> Optional[State]:
  # get the html report as a string
  report = flow.executor.performance_report

  # now we can write to S3, GCS, Azure Blob
  # or perform any other custom logic with the report
  
  # for example, saving the report to s3
  s3_client = get_boto_client("s3")
  report_data = io.BytesIO(report.encode())
  s3_client.upload_fileobj(report_data, Bucket="my-bucket", Key="performance_report.html")

# define a simple task and flow
@task
def hello():
  return "hi"

with Flow('performance_report') as flow:
  x = hello()

# specify where the executor should write the performance report
# in this case we just write to a temporary directory
flow.executor = DaskExecutor(performance_report_path="/tmp/performance_report.html")

# specify a terminal state handler for custom logic
flow.terminal_state_handler = custom_terminal_state_handler
```

To register the flow

```bash
prefect register -p performance_report_flow.py 
```

Then, execute the flow with an agent. The performance report will be generated and
written to the location specified in `custom_terminal_state_handler`.
