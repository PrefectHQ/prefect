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

```python hl_lines="4"
from prefect import flow
from prefect.task_runners import DaskTaskRunner

@flow(task_runner=DaskTaskRunner())
def my_flow():
    pass
```

If a task runner type is passed, a task runner instance will be created with the default settings. Task runner instances can be passed for additional configuration:

```python hl_lines="4"
from prefect import flow
from prefect.task_runner import DaskTaskRunner

@flow(task_runner=DaskTaskRunner(address="http://my-dask-cluster"))
def my_flow():
    pass
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

my_flow()
```

This script outputs the following logs demonstrating the temporary Dask task runner:

```text hl_lines="7"
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

Check out the [Dask task runner tutorial](/tutorials/dask-task-runner/) for some common Dask use cases.

