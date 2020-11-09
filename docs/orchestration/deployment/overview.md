# Deployment Overview

When deploying flows using Prefect Cloud or Server, flows need some additional
configuration not used when deploying flows locally:

- **Storage**: describes where the flow should be stored to and loaded from
  during execution.

- **Run Configuration**: describes where and how a flow run should be executed.

## Storage

`Storage` objects define where a Flow should be stored. Examples include things
like `Local` storage (which uses the local filesystem) or `S3` (which stores
flows remotely on AWS S3). Flows themselves are never stored directly in
Prefect's backend; only a reference to the storage location is persisted. This
helps keep your flow's code secure, as the Prefect servers never have direct
access.

To configure a Flow's storage, you can either specify the `storage` as part of
the `Flow` constructor, or set it as an attribute later before calling
`flow.register`. For example, to configure a flow to use `Docker` storage:

```python
from prefect import Flow
from prefect.environments.storage import Docker

# Set storage as part of the constructor
with Flow("example", storage=Docker()) as flow:
    ...

# OR set storage as an attribute later
with Flow("example") as flow:
    ...

flow.storage = Docker()
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

To configure a Flow's `run_config`, you can either specify the `run_config` as
part of the `Flow` constructor, or set it as an attribute later before calling
`flow.register`. For example, to configure a flow to run on Kubernetes:

```python
from prefect import Flow
from prefect.run_configs import KubernetesRun

# Set run_config as part of the constructor
with Flow("example", run_config=KubernetesRun()) as flow:
    ...

# OR set run_config as an attribute later
with Flow("example") as flow:
    ...

flow.run_config = KubernetesRun()
```

For more information on the different `RunConfig` types, see the
[RunConfig docs](/api/latest/run_configs.md).

### Labels

[Like Agents](../agents/overview.md#flow-affinity:-labels), `RunConfig` objects
can be configured with zero or more labels.  Labels can be used to determine
which agent (or agents) can execute a flow; for an agent to receive a flow run
to execute, the labels set on the agent must be a *superset* of those set on
the `RunConfig`.

For example, here we configure a flow with `labels=["dev", "ml"]`:

```python
from prefect import Flow
from prefect.run_configs import LocalRun

# Configure a flow with a `dev` label
flow = Flow(
    "example",
    run_config=LocalRun(labels=["dev", "ml"])
)
```

An agent running with `labels=["dev", "staging", "ml"]` would be able to
execute this flow, since the agent's labels are a *superset* of those on the
flow. In contrast, an agent running with `labels=["dev", "staging"]` would
not, since the agent's labels are not a *superset* of those on the flow.

:::tip Empty Labels
An empty label list is effectively considered a label. This means that if you
register a flow with no labels it will only be picked up by Agents which also
do not have labels specified.
:::
