# Task runners

Task runners are responsible for running Prefect tasks. Each flow has a task runner associated with it. The task runner is started at the beginning of a flow run and shutdown at the end.

Depending on the task runner you use, the tasks within your flow can run in parallel or sequentially. The default task runner is the `SequentialTaskRunner`, which does not run your tasks in parallel. To run tasks in parallel, you can use a task runner such as the `DaskTaskRunner`, which enables Dask-based parallel execution.

[[toc]]

## Using an task runner

Import task runners from `prefect.task_runners` and assign them when the flow is defined.

```python hl_lines="4"
from prefect import flow
from prefect.task_runners import DaskTaskRunner

@flow(task_runner=DaskTaskRunner())
def my_flow():
    pass
```

If a task runner type is passed, a task runner instance will be created with the default settings. TaskRunner instances can be passed for additional configuration:


```python hl_lines="4"
from prefect import flow
from prefect.task_runner import DaskTaskRunner

@flow(task_runner=DaskTaskRunner(address="http://my-dask-cluster"))
def my_flow():
    pass
```

## Using multiple task runners

Each flow can only have a single task runner, but sometimes you may want a subset of your tasks to run elsewhere. In this case, you can create [subflows](/concepts/flows/#subflows) to temporarily use a different task runner.

For example, you can have a flow (`my_flow`) that runs its tasks locally, but uses a subflow (`my_subflow`) to run some tasks in a Dask cluster.

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
def my_flow():
    hello_local()
    my_subflow()
    hello_local()

@flow(task_runner=DaskTaskRunner())
def my_subflow():
    hello_dask()

my_flow()
```

This script outputs the following logs demonstrating the temporary Dask task runner:

```text hl_lines="7"
13:46:58.865 | Beginning flow run 'olivine-swan' for flow 'my-flow'...
13:46:58.866 | Starting task runner `SequentialTaskRunner`...
13:46:58.934 | Submitting task run 'hello_local-a087a829-0' to task runner...
Hello!
13:46:58.955 | Task run 'hello_local-a087a829-0' finished in state Completed(message=None, type=COMPLETED)
13:46:58.981 | Beginning subflow run 'discreet-peacock' for flow 'my-subflow'...
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

## TaskRunner types

See the [`prefect.task_runners` API reference](/api-ref/prefect/task-runners/) for descriptions of each task runner.

Check out the [Dask task runner tutorial](/tutorials/dask-task-runner/) for some common Dask use cases.

## Task run concurrency limits

There are situations in which you want to actively prevent too many tasks from running simultaneously. For example, if many tasks across multiple flows are designed to interact with a database that only allows 10 connections, you want to make sure that no more than 10 tasks that connect to this database are running at any given time.

Prefect has built-in functionality for achieving this: task concurrency limits.

Task concurrency limits use [task tags](/concepts/tasks.md#tags) &mdash; you can assign as many tags as you wish to a task, and you can specify an optional concurrency limit as the maximum number of concurrent task runs for tasks with that tag. 

If a task has multiple tags, it will run only if _all_ tags have available concurrency. 

Tags without explicit limits are considered to have unlimited concurrency.

!!! note 0 concurrency limit aborts task runs 

    Currently, if the concurrency limit is set to 0 for a tag, any attempt to run a task with that tag will be aborted instead of delayed.

!!! warning Concurrency limits in subflows

    Using concurrency limits on task runs in subflows can cause deadlocks. As a best practice, configure your tags and concurrency limits to avoid setting limits on task runs in subflows.

### Execution behavior

Task tag limits are checked whenever a task run attempts to enter a [`Running` state](/concepts/states.md). 

If there are no concurrency slots available for any one of your task's tags, the task run will instead enter a `Queued` state. The same Python process that is attempting to run the task will then attempt to re-enter a `Running` state every 30 seconds (this value is configurable via `config.cloud.queue_interval`). 

Additionally, if that process ever fails, Prefect will create a new runner every 10 minutes, which will then attempt to rerun your task on the specified queue interval. This process will repeat until all requested concurrency slots become available.

### Configuring concurrency limits

You can set concurrency limits on as few or as many tags as you wish. You can set limits through the CLI or via API by using the `OrionClient`.

#### CLI

You can create, list, and remove concurrency limits by using Prefect ClI `concurrency-limit` commands.

```bash
$ prefect concurrency_limit [command] [arguments]
```

| Command | Description |
| --- | --- |
| create | Create a concurrency limit by specifying a tag and limit. |
| delete | Delete the concurrency limit set on the specified tag. |
| ls     | View all defined concurrency limits. |
| read   | View details about a concurrency limit. `active_slots` shows a list of IDs for task runs that are currently using a concurrency slot. |

For example, to set a concurrency limit of 10 on the 'small_instance' tag:

```bash
$ prefect concurrency_limit create small_instance 10
```

To delete the concurrency limit on the 'small_instance' tag:

```bash
$ prefect concurrency_limit delete small_instance
```

#### Python client

To update your tag concurrency limits programmatically, use [`OrionClient.create_concurrency_limit`](/api-ref/prefect/client/#prefect.client.OrionClient.create_concurrency_limit). 

`create_concurrency_limit` takes two arguments:

- `tag` specifies the task tag on which you're setting a limit.
- `concurrency_limit` specifies the maximum number of concurrent task runs for that tag.

For example, to set a concurrency limit of 10 on the 'small_instance' tag:

```python
from prefect.client import OrionClient

with OrionClient as client:
    # set a concurrency limit of 10 on the 'small_instance' tag
    limit_id = client.create_concurrency_limit(tag="small_instance", concurrency_limit=10)
```

To remove all concurrency limits on a tag, use [`OrionClient.delete_concurrency_limit_by_tag`](/api-ref/prefect/client/#prefect.client.OrionClient.delete_concurrency_limit_by_tag), passing the tag:

```python
with OrionClient as client:
    # remove a concurrency limit on the 'small_instance' tag
    client.delete_concurrency_limit_by_tag(tag="small_instance")
```

If you wish to query for the currently set limit on a tag, use [`OrionClient.read_concurrency_limit_by_tag`](/api-ref/prefect/client/#prefect.client.OrionClient.read_concurrency_limit_by_tag), passing the tag:

To see _all_ of your limits across all of your tags, use [`OrionClient.read_concurrency_limits`](/api-ref/prefect/client/#prefect.client.OrionClient.read_concurrency_limits).

```python
with OrionClient as client:
    # query the concurrency limit on the 'small_instance' tag
    limit = client.read_concurrency_limit_by_tag(tag="small_instance")
```
