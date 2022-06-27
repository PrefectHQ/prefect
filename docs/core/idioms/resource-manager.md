# Managing temporary resources

Sometimes you have workloads that depend on resources that need to be setup,
used, then cleaned up. Examples might include:

- Compute resources like Dask or Spark clusters
- Cloud resources like Virtual machines or Kubernetes deployments
- Docker containers
- ...

To simplify this pattern, Prefect provides a
[`ResourceManager`](/api/latest/tasks/resources.html) object for
encapsulating the setup and cleanup tasks for resources. The most common way
to define a `ResourceManager` is using the `resource_manager` decorator. This
decorator wraps a class with the following methods:

- `__init__`:  Initializes the resource manager with whatever arguments are needed.
- `setup`: Creates the resource. Takes no arguments, and may optionally
  return a value that can be used by downstream tasks.
- `cleanup`: Cleans up the resource. Takes the result of `setup` as an argument.

```python
from prefect import resource_manager

@resource_manager
class MyResource:
    def __init__(self, ...):
        """Initialize the resource manager.

        This should store any values required by the setup and cleanup steps.
        """
        ...

    def setup(self):
        """Setup the resource.

        The result of this method can be used in downstream tasks.
        """
        ...

    def cleanup(self, resource):
        """Cleanup the resource.

        This receives the result of `setup`, and is always called if `setup`
        succeeds, even if other upstream tasks failed.
        """
        ...
```

The resulting `ResourceManager` can then be used when building a `Flow` as a
context-manager around tasks that rely on that resource. The resource will be
created upon entering the context block, and will be cleaned up upon exiting
the block, even if tasks contained inside the context fail.

```python
with Flow("example") as flow:
    with MyResource(...) as resource:
        some_task(resource)
        other_task(resource)
```

`ResourceManager` objects are intended for defining resources where the cleanup
of the resource should also be monitored and managed by Prefect as a `Task` in
your `Flow`. This is good for things that can be expensive, like cloud
resources. For things where a failure to cleanup an object isn't detrimental
(like e.g. a `boto` client) you may be better off relying on other patterns.

## Example: Creating a temporary Dask Cluster

Here we provide a full example for using a `ResourceManager` to setup and
cleanup a temporary [Dask](https://dask.org) cluster.

Functional API:
```python
from prefect import Flow, task, resource_manager, Parameter
import dask
from dask.distributed import Client

@resource_manager
class DaskCluster:
    """Create a temporary dask cluster.

    Args:
        - n_workers (int, optional): The number of workers to start.
    """
    def __init__(self, n_workers=None):
        self.n_workers = n_workers

    def setup(self):
        """Create a temporary dask cluster, returning the `Client`"""
        return Client(n_workers=self.n_workers)

    def cleanup(self, client):
        """Shutdown the temporary dask cluster"""
        client.close()

@task
def load_data():
    """Load some data"""
    return dask.datasets.timeseries()

@task
def summarize(df, client):
    """Compute a summary on the data"""
    return df.describe().compute()

@task
def write_csv(df, path):
    """Write the summary to disk as a csv"""
    return df.to_csv(path, index_label="index")


with Flow("dask-example") as flow:
    n_workers = Parameter("n_workers", default=None)
    out_path = Parameter("out_path", default="summary.csv")

    with DaskCluster(n_workers=n_workers) as client:
        # These tasks rely on a dask cluster to run, so we create them inside
        # the `DaskCluster` resource manager
        df = load_data()
        summary = summarize(df, client)

    # This task doesn't rely on the dask cluster to run, so it doesn't need to
    # be under the `DaskCluster` context
    write_csv(summary, out_path)
```

Imperative API:
```python
from prefect import Flow, Task, resource_manager, Parameter
import dask
from dask.distributed import Client

@resource_manager
class DaskCluster:
    """Create a temporary dask cluster.

    Args:
        - n_workers (int, optional): The number of workers to start.
    """
    def __init__(self, n_workers=None):
        self.n_workers = n_workers

    def setup(self):
        """Create a temporary dask cluster, returning the `Client`"""
        return Client(n_workers=self.n_workers)

    def cleanup(self, client):
        """Shutdown the temporary dask cluster"""
        client.close()

class LoadData(Task):
    """Load some data"""
    def run(self):
        return dask.datasets.timeseries()

class Summarize(Task):
    """Compute a summary on the data"""
    def run(self, df, client):
        return df.describe().compute()

class WriteCSV(Task):
    """Write the summary to disk as a csv"""
    def run(self, df, path):
        return df.to_csv(path, index_label="index")


flow = Flow("dask-example")
n_workers = Parameter("n_workers", default=None)
out_path = Parameter("out_path", default="summary.csv")

with DaskCluster(n_workers=n_workers, flow=flow) as client:
    # These tasks rely on a dask cluster to run, so we create them inside
    # the `DaskCluster` resource manager
    df = LoadData()
    summary = Summarize().bind(df, client, flow=flow)

# This task doesn't rely on the dask cluster to run, so it doesn't need to
# be under the `DaskCluster` context
WriteCSV().bind(summary, out_path, flow=flow)
```

