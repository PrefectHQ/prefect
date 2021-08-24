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
from prefect.storage import Docker

with Flow("example", storage=Docker()) as flow:
    ...
```

For more information on the different `Storage` types, see the
[Storage docs](./storage.md).

## Run Configuration

`RunConfig` objects define where and how a flow run should be executed. Each
`RunConfig` type has a corresponding Prefect Agent (i.e. `LocalRun` pairs with
a Local Agent, `DockerRun` pairs with a Docker Agent, ...). The options
available on a `RunConfig` depend on the type, but generally include options
for setting environment variables, configuring resources (CPU/memory), or
selecting a [docker image](./docker.md) to use (if not using `Docker` storage). 

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

A flow's `Executor` is responsible for executing tasks in a flow run. There are
several different options, each with different performance characteristics.
Choosing a good executor configuration can greatly improve your flow's
performance.

A flow's `executor` is configured on the flow itself. For example, to configure
a flow to use a `LocalDaskExecutor`:

```python
from prefect import Flow
from prefect.executors import LocalDaskExecutor

with Flow("example", executor=LocalDaskExecutor()) as flow:
    ...
```

For more information on the different `Executor` options, see the
[Executor docs](./executors.md)


## Next steps

Hopefully you have an understanding of how to configure your flow for deployment with the Prefect backend. Take a look at some related docs next:

- Before you can run your configured flow, it needs to be registered with the backend; check out the [flow registration documentation](/orchestration/concepts/flows.md#registration)
- To run your registered flow, you need to create flow runs; check out [the flow run documentation](/orchestration/flow_run/overview.md)