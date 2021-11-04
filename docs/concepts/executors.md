# Executors

Executors are responsible for running Prefect tasks. Each flow has an executor associated with it. The executor is started at the beginning of a flow run and shutdown at the end.

Depending on the executor you use, the tasks within your flow can run in parallel or seqentially. The default executor is the `SequentialExecutor`, which does not run your tasks in parallel. To run tasks in parallel, you can use an executor such as the `DaskExecutor`, which enables Dask-based parallel execution.

## Using an executor

Import executors from `prefect.executors` and assign them when the flow is defined.

```python
from prefect import flow
from prefect.executors import DaskExecutor

@flow(executor=DaskExecutor)
def my_flow():
    pass
```

If an executor type is passed, an executor instance will be created with the default settings. Executor instances can be passed for additional configuration:


```python
from prefect import flow
from prefect.executors import DaskExecutor

@flow(executor=DaskExecutor(address="http://my-dask-cluster"))
def my_flow():
    pass
```

## Using multiple executors

Each flow can only have a single executor, but sometimes you may want a subset of your tasks to run elsewhere. In this case, you can create [subflows](/concepts/flows/#subflows) to temporarily use a different executor.

For example, you can have a flow (`my_flow`) that runs its tasks locally, but uses a subflow (`my_subflow`) to run some tasks in a Dask cluster.

```python
from prefect import flow, task
from prefect.executors import DaskExecutor, SequentialExecutor

@task
def hello_local():
    print("Hello!")

@task
def hello_dask():
    print("Hello from Dask!")

@flow(executor=SequentialExecutor)
def my_flow():
    hello_local()
    my_subflow()
    hello_local()

@flow(executor=DaskExecutor)
def my_subflow():
    hello_dask()

my_flow()
```

This script outputs the following logs:

```
13:46:58.865 | Beginning flow run 'olivine-swan' for flow 'my-flow'...
13:46:58.866 | Starting executor `SequentialExecutor`...
13:46:58.934 | Submitting task run 'hello_local-a087a829-0' to executor...
Hello!
13:46:58.955 | Task run 'hello_local-a087a829-0' finished in state Completed(message=None, type=COMPLETED)
13:46:58.981 | Beginning subflow run 'discreet-peacock' for flow 'my-subflow'...
13:46:58.981 | Starting executor `DaskExecutor`...
13:46:58.981 | Creating a new Dask cluster with `distributed.deploy.local.LocalCluster`
13:46:59.339 | The Dask dashboard is available at http://127.0.0.1:8787/status
13:46:59.369 | Submitting task run 'hello_dask-e80d21db-0' to executor...
Hello from Dask!
13:47:00.066 | Task run 'hello_dask-e80d21db-0' finished in state Completed(message=None, type=COMPLETED)
13:47:00.070 | Shutting down executor `DaskExecutor`...
13:47:00.294 | Subflow run 'discreet-peacock' finished in state Completed(message='All states completed.', type=COMPLETED)
13:47:00.305 | Submitting task run 'hello_local-a087a829-1' to executor...
Hello!
13:47:00.325 | Task run 'hello_local-a087a829-1' finished in state Completed(message=None, type=COMPLETED)
13:47:00.326 | Shutting down executor `SequentialExecutor`...
13:47:00.334 | Flow run 'olivine-swan' finished in state Completed(message='All states completed.', type=COMPLETED)
```

## Executor types

See the [`prefect.executors` API reference](/api-ref/prefect/executors/) for descriptions of each executor type.

Check out the [Dask executor tutorial](/tutorials/dask-executor/) for some common Dask use cases.
