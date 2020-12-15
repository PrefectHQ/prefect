# Execution Overview

::: warning
Flows configured with environments are being deprecated - we recommend users
transition to using "Run Configs" instead. See [flow
configuration](/orchestration/flow_config/overview.md) and [upgrading
tips](/orchestration/flow_config/upgrade.md) for more information.
:::

Executing flows using the Prefect API is accomplished through two powerful abstractions — storage and environments. By combining these two abstractions, flows can be saved, shared, and executed across various platforms.

[[toc]]

## Storage

[Storage](https://docs.prefect.io/api/latest/storage.html) objects are pieces of functionality which define how and where a Flow should be stored. Prefect supports storage options ranging from ephemeral in-memory storage to Docker images which can be stored in registries.

### How Storage is Used

To attach storage to your Flows, provide your storage object at initialization:

```python
from prefect.storage import Docker

f = Flow("example-storage", storage=Docker(registry_url="prefecthq/storage-example"))
```

or assign it directly:

```python
from prefect.storage import Docker

f = Flow("example-storage")
f.storage = Docker(registry_url="prefecthq/storage-example")
```

When you register your flow with the Prefect API the storage object attached to the flow will be built. At this step the flow is serialized to byte code and placed inside of the storage. For added convenience, `flow.register` will accept arbitrary keyword arguments which will then be passed to the initialization method of your configured default storage class (which is `Local` by default). The following code will actually pass the `registry_url` to the `Docker` Storage object for you at registration-time and push that image to your specified registry:

```python
from prefect import Flow
from prefect.storage import Docker

f = Flow("example-easy-storage")
f.storage = Docker()

# all other init kwargs to `Docker` are accepted here
f.register("My First Project", registry_url="prefecthq/storage-example")
```

::: tip Pre-Build Storage
You are also able to optionally build your storage separate from the `register` command and specify that you do not want to build it again at registration-time:

```python
from prefect.storage import Docker

f = Flow("example-storage")
f.storage = Docker(registry_url="prefecthq/storage-example")

# Pre-build storage
f.storage.build()

# Register but don't rebuild storage
f.register("My First Project", build=False)
```

:::

## Environments

While Storage objects provide a way to save and retrieve Flows, [Environments](https://docs.prefect.io/api/latest/environments/execution.html) specify _how your Flow should be run_ e.g., which executor to use and whether there are any auxiliary infrastructure requirements for your Flow's execution. For example, if you want to run your Flow on Kubernetes using an auto-scaling Dask cluster then you're going to want to use an environment for that!

### How Environments are Used

By default, Prefect attaches `LocalEnvironment` with your local default
executor to every Flow you create. To specify a different environment, provide
it to your Flow at initialization:

```python
from prefect.executors import DaskExecutor
from prefect.environments import LocalEnvironment

f = Flow("example-env", environment=LocalEnvironment(executor=DaskExecutor()))
```

or assign it directly:

```python
from prefect.executors import DaskExecutor
from prefect.environments import LocalEnvironment

f = Flow("example-env")
f.environment = LocalEnvironment(executor=DaskExecutor())
```

### Setup & Execute

The two main environment functions are `setup` and `execute`. The `setup` function is responsible for creating or prepping any infrastructure requirements before the Flow is executed e.g., spinning up a Dask cluster or checking available platform resources. The `execute` function is responsible for actually telling the Flow where and how it needs to run e.g., running the Flow in process, as per the [`LocalEnvironment`](https://docs.prefect.io/api/latest/environments/execution.html##localenvironment), or registering a new Fargate task, as per the [`FargateTaskEnvironment`](https://docs.prefect.io/api/latest/environments/execution.html#fargatetaskenvironment).

### Environment Callbacks

Each Prefect environment has two optional arguments - `on_start` and `on_exit` - which can be used to add functionality outside of infrastructure or Flow-related processes. The `on_start` callback is executed before the Flow starts in the main process; the `on_exit` callback is executed after the Flow finishes.

_For more information on the design behind Environment Callbacks visit [PIN 12](/core/PINs/PIN-12-Environment-Callbacks.html)._

#### Callback Example

In this example we have a function called `report_cluster_metrics` which, when
run on a Kubernetes cluster, gathers information about current resource usage.
We can use this to track resource usage both before and after a Flow run.

```python
from prefect import Flow, task
from prefect.environments import LocalEnvironment


# Report cluster metrics that we will use before and after Flow run
def report_cluster_metrics():
    get_me_some_metrics()


@task
def extract():
    """Get a list of data"""
    return [1, 2, 3]


@task
def transform(data):
    """Multiply the input by 10"""
    return [i * 10 for i in data]


@task
def load(data):
    """Print the data to indicate it was received"""
    print("Here's your data: {}".format(data))


# Attach out metrics reporting callbacks
environment = LocalEnvironment(
    on_start=report_cluster_metrics,
    on_exit=report_cluster_metrics
)


with Flow("Callback-Example", environment=environment) as flow:
    e = extract()
    t = transform(e)
    l = load(t)
```

### Labels

Environments expose a configurable list of `labels`, allowing you to label your Flows and determine where they are executed. This works in conjunction with the list of `labels` you may provide on your [Prefect Agents](../agents/overview.html#flow-affinity:-labels).

#### Label Example

An Agent's labels must be a superset of the labels specified on a Flow's environment. This means that if a Flow's environment labels are specified as `["dev"]` and an Agent is running with labels set to `["dev", "staging"]`, the agent will run that Flow because the _dev_ label is a subset of the labels provided to the Agent.

```python
from prefect.environments import LocalEnvironment

f = Flow("example-label")
f.environment = LocalEnvironment(labels=["dev"])
```

```python
from prefect.agent.local import LocalAgent

LocalAgent(labels=["dev", "staging"]).start()

# Flow will be picked up by this agent
```

On the other hand if you register a flow that has environment labels set to `["dev", "staging"]` and run an Agent with the labels `["dev"]` then it will not pick up the flow because there exists labels in the environment which were not provided to the agent.

```python
from prefect.environments import LocalEnvironment

f = Flow("example-label")
f.environment = LocalEnvironment(labels=["dev", "staging"])
```

```python
from prefect.agent.local import LocalAgent

LocalAgent(labels=["dev"]).start()

# Flow will NOT be picked up by this agent
```

:::tip Empty Labels
An empty label list is effectively considered a label. This means that if you register a flow with no environment labels it will only be picked up by Agents which also do not have labels specified.
:::
