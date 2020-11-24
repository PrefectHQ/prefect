# Overview

When deploying flows using Prefect Cloud or Server, flows need some additional
configuration not used when deploying flows locally:

- **Storage**: describes where the flow should be stored to and loaded from
  during execution.

- **Run Configuration**: describes where and how a flow run should be executed.

- **Executor**: describes where and how *tasks* in a flow run should be executed.

## Storage

`Storage` objects define where a Flow should be stored. Examples include things
like `Local` storage (which uses the local filesystem) or `S3` (which stores
flows remotely on AWS S3). Flows themselves are never stored directly in
Prefect's backend; only a reference to the storage location is persisted. This
helps keep your flow's code secure, as the Prefect servers never have direct
access.

For example, to configure a flow to use `Docker` storage:

```python
from prefect import Flow
from prefect.environments.storage import Docker

with Flow("example", storage=Docker()) as flow:
    ...
```

For more information on the different `Storage` types, see
[Storage](./storage.md).

## Run Configuration

`RunConfig` objects define where and how a flow run should be executed. Each
`RunConfig` type has a corresponding Prefect Agent (i.e. `LocalRun` pairs with
a Local Agent, `DockerRun` pairs with a Docker Agent, ...). The options
available on a `RunConfig` depend on the type, but generally include options
for setting environment variables, configuring resources (CPU/memory), or
selecting a docker image to use (if not using `Docker` storage). 

For example, to configure a flow to run on Kubernetes:

```python
from prefect import Flow
from prefect.run_configs import KubernetesRun

with Flow("example", run_config=KubernetesRun()) as flow:
    ...
```

For more information on the different `RunConfig` types, see the
[RunConfig docs](./run_configs.md).

## Executor

A flow's `Executor` is responsible for running tasks in a flow. The default
[LocalExecutor](/api/latest/engine/executors.md#local) executes all tasks
locally in a single thread. For parallel execution you can switch to the
[LocalDaskExecutor](/api/latest/engine/executors.md#localdaskexecutor) to run
using local threads or processes. There's also the
[DaskExecutor](/api/latest/engine/executors.md#daskexecutor) for larger flow
runs where distributed execution is necessary.

To configure an executor on a flow, you can specify it as part of the
constructor, or set it as the `executor` attribute later before calling
`flow.register`. For example, to configure a flow to use a `LocalDaskExecutor`:

```python
from prefect import Flow
from prefect.engine.executors import LocalDaskExecutor

# Set executor as part of the constructor
with Flow("example", executor=LocalDaskExecutor()) as flow:
    ...

# OR set executor as an attribute later
with Flow("example") as flow:
    ...

flow.executor = LocalDaskExecutor()
```

For more information on the different `Executor` types, see the
[Executor docs](/api/latest/engine/executors.md).
