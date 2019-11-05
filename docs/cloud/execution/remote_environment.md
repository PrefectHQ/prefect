# Remote Environment

[[toc]]

## Overview

The Remote Environment is the default environment for all Flows that are deployed to Prefect Cloud. This environment is meant to be a simple and minimally configurable execution environment for Flow runs. The Remote Environment functions as a way to execute Flows without any pre-existing infrastructure requirements and instead opts to run Flows directly in process. The only needed configuration for the Remote Environment is the specification of an [Executor](/core/concepts/engine.html#executors) however if it is not specified then it defaults to the [LocalExecutor](/api/unreleased/engine/executors.html#localexecutor).

*For more information on the Remote Environment visit the relevant [API documentation](/api/unreleased/environments/execution.html#remoteenvironment).*

## Process

#### Initialization

The `RemoteEnvironment` can optionally accept two arguments `executor` and `executor_kwargs`. The `executor` argument accepts a string representation of an import path for a Prefect Executor (e.g. _prefect.engine.executors.DaskExecutor_) and the `executor_kwargs` accepts a dictionary of additional keyword arguments to pass to the Executor (e.g. passing an _address_ to the [DaskExecutor](/api/unreleased/engine/executors.html#daskexecutor)).

#### Setup

The Remote Environment has no setup step because there are not any infrastructure requirements that are needed for using this environment.

#### Execute

Run the Flow right there in process using the specified Executor configuration from the `executor` and `executor_kwargs` that were provided at initialization. This means that if something like the [DaskExecutor](/api/unreleased/engine/executors.html#daskexecutor) was specified then it will connect to the Dask scheduler address as specified in the `executor_kwargs`.

## Examples

#### Remote Environment w/ Local Executor

The following example is the same functionality as deploying a Flow to Prefect Cloud without specifying an Environment because the `RemoteEnvironment` using the `LocalExecutor` is the default.

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
)

# set task dependencies using imperative API
output_value.set_upstream(get_value, flow=flow)
output_value.bind(value=get_value, flow=flow)
```
