# Local Environment

!!! warning
    Flows configured with environments are no longer supported. We recommend users transition to using [RunConfig](/orchestration/flow_config/run_configs.html) instead. See the [Flow Configuration](/orchestration/flow_config/overview.md) and [Upgrading Environments to RunConfig](/orchestration/faq/upgrade_environments.md) documentation for more information.


[[toc]]

## Overview

The Local Environment (`LocalEnvironment`) is meant to be a simple and
minimally configurable execution Environment for Flow runs, and is the default
Environment for all Flows registered with the Prefect API. The Local
Environment functions as a way to execute Flows without any pre-existing
infrastructure requirements and instead opts to run Flows directly in process.

The only needed configuration for the Local Environment is the specification
of an [Executor](/core/concepts/engine.html#executors) however if it is not
specified then it defaults to the
[LocalExecutor](/api/latest/executors.html#localexecutor).

_For more information on the Local Environment visit the relevant [API
documentation](/api/latest/environments/execution.html#localenvironment)._

## Process

#### Initialization

The `LocalEnvironment` takes an optional `executor` argument.  The `executor`
argument accepts an [Executor](/core/concepts/engine.html#executors) object
that should be used to run this flow. If not specified, the local default
executor is used.

#### Setup

The `LocalEnvironment` has no setup step because it has no infrastructure
requirements.

#### Execute

The `LocalEnvironment` executes the flow locally in process, using the
configured `executor`.

## Examples

#### Using a LocalExecutor

Here we configure a `LocalEnvironment` to run a flow using a `LocalExecutor`.
Note that this is the same as the default behavior - if you don't specify an
`environment` on a `Flow` the same configuration will be created for you.

```python
from prefect import Flow
from prefect.environments import LocalEnvironment
from prefect.executors import LocalExecutor

flow = Flow(
    "Local Executor Example",
    environment=LocalEnvironment(executor=LocalExecutor()),
)
```

#### Using a DaskExecutor, with a local Dask cluster

Here we configure a `LocalEnvironment` to run a flow using a
[DaskExecutor](/api/latest/executors.html#daskexecutor), connected to a
local temporary [Dask](https://dask.org") cluster. When the flow run starts, a
temporary local Dask cluster will be created just for that flow run.

```python
from prefect import Flow
from prefect.environments import LocalEnvironment
from prefect.executors import DaskExecutor

flow = Flow(
    "Dask Executor Example",
    environment=LocalEnvironment(executor=DaskExecutor())
)
```

#### Using a DaskExecutor, with an existing Dask cluster

Here we configure a `LocalEnvironment` to run a flow using a `DaskExecutor`,
connected to an existing Dask cluster.

```python
from prefect import Flow
from prefect.environments import LocalEnvironment
from prefect.executors import DaskExecutor

flow = Flow(
    "Dask Executor Example",
    environment=LocalEnvironment(
        executor=DaskExecutor(
            "tcp://address-of-the-dask-cluster:8786",
        )
    )
)
```
