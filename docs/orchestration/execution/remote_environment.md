# Remote Environment

[[toc]]

## Overview

The Remote Environment (`RemoteEnvironment`) is meant to be a simple and minimally configurable execution Environment for Flow runs, and is the default Environment for all Flows registered with the Prefect API. The Remote Environment functions as a way to execute Flows without any pre-existing infrastructure requirements and instead opts to run Flows directly in process. The only needed configuration for the Remote Environment is the specification of an [Executor](/core/concepts/engine.html#executors) however if it is not specified then it defaults to the [LocalExecutor](/api/latest/engine/executors.html#localexecutor).

_For more information on the Remote Environment visit the relevant [API documentation](/api/latest/environments/execution.html#remoteenvironment)._

## Process

#### Initialization

The `RemoteEnvironment` can optionally accept two arguments: `executor` and `executor_kwargs`. The `executor` argument accepts a string representation of an import path for a Prefect Executor (e.g. _prefect.engine.executors.DaskExecutor_) and the `executor_kwargs` accepts a dictionary of additional keyword arguments to pass to the Executor (e.g. passing an _address_ to the [DaskExecutor](/api/latest/engine/executors.html#daskexecutor)).

#### Setup

The `RemoteEnvironment` has no setup step because it has no infrastructure requirements.

#### Execute

You can run your Flow in process using the Executor configuration specified in the `executor` and `executor_kwargs` you provided at Flow initialization. As an example, if the [DaskExecutor](/api/latest/engine/executors.html#daskexecutor) was specified, it will connect to the Dask scheduler address specified in the `executor_kwargs`.

## Examples

#### Remote Environment w/ Local Executor

The following example is the same functionality as registering a Flow with the Prefect API without specifying an Environment because the `RemoteEnvironment` using the `LocalExecutor` is the default.

```python
from prefect import task, Flow
from prefect.environments import RemoteEnvironment


@task
def get_value():
    return "Example!"


@task
def output_value(value):
    print(value)


flow = Flow(
    "Local Executor Remote Example",
    environment=RemoteEnvironment(executor="prefect.engine.executors.LocalExecutor"),
)

# set task dependencies using imperative API
output_value.set_upstream(get_value, flow=flow)
output_value.bind(value=get_value, flow=flow)
```

#### Remote Environment w/ Dask Executor

```python
from prefect import task, Flow
from prefect.environments import RemoteEnvironment
from prefect.environments.storage import Docker

@task
def get_value():
    return "Example!"


@task
def output_value(value):
    print(value)


flow = Flow(
    "Dask Executor Remote Example",
    environment=RemoteEnvironment(
        executor="prefect.engine.executors.DaskExecutor",
        executor_kwargs={
            "address": "tcp://127.0.0.1:8786"  # Address of a Dask scheduler
        },
    ),
    storage=Docker(
        registry_url="gcr.io/dev/", image_name="k8s-job-flow", image_tag="0.1.0"
    ),
)

# set task dependencies using imperative API
output_value.set_upstream(get_value, flow=flow)
output_value.bind(value=get_value, flow=flow)
```
