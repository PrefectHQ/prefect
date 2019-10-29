# Execution

Executing your flows using Prefect Cloud is accomplished through two powerful abstractions—storage and environments. By combining Prefect's concepts of storage and environments, flows are able to be saved, shared, and executed across various supported platforms.

[[toc]]

## Storage

[Storage](https://docs.prefect.io/api/unreleased/environments/storage.html) objects are pieces of functionality which define how and where a flow should be stored. Prefect currently has support for storage options ranging from ephemeral in-memory storage to Docker images which can be stored in registries.

::: tip Cloud Acceptable Storage
Currently the only supported Storage class in Prefect Cloud is [Docker storage](https://docs.prefect.io/api/unreleased/environments/storage.html#docker). This is due to the fact that Prefect Cloud does not retrieve the storage object itself and only cares about metadata describing the location of the image.
:::

### How Storage is Used

To attach storage to your flows simply provide your storage object at initialization:

```python
from prefect.environments.storage import Docker

f = Flow("example-storage", storage=Docker(registry_url="prefecthq/storage-example"))
```

or assign it directly:

```python
from prefect.environments.storage import Docker

f = Flow("example-storage")
f.storage = Docker(registry_url="prefecthq/storage-example")
```

When you deploy your flow to Prefect Cloud the storage object attached to the flow will be built. At this step the flow is serialized to byte code and placed inside of the storage. For added convenience, `flow.deploy` will accept arbitrary keyword arguments which will then be passed to the initialization method of your configured default storage class (which is `Docker` by default). Consequently, the following code will actually create a `Docker` object for you at deploy-time and push that image to your specified registry:

```python
from prefect import Flow

f = Flow("example-easy-storage")

# all other init kwargs to `Docker` are accepted here
f.deploy("My First Project", registry_url="prefecthq/storage-example")
```

::: tip Pre-Build Storage
You are also able to optionally build your storage separate from the `deploy` command and specify that you do not want to build it again at deploy time:

```python
from prefect.environments.storage import Docker

f = Flow("example-storage")
f.storage = Docker(registry_url="prefecthq/storage-example")

# Pre-build storage
f.storage.build()

# Deploy but don't rebuild storage
f.deploy("My First Project", build=False)
```

:::

## Environments

While Storage objects provide a way to save and retrieve flows, [Environments](https://docs.prefect.io/api/unreleased/environments/execution.html) are a mechanism for specifying execution information about _how your Flow should be run_. For example, what executor should be used and are there any auxiliary infrastructure requirements for your Flow's execution? For example, if you want to run your flow on Kubernetes using an auto-scaling Dask cluster then you're going to want to use an environment for that!

### How Environments are Used

By default, Prefect will attach a `RemoteEnvironment` with your local default executor to every Flow you create. To specify a different environment, simply provide it to your Flow at initialization:

```python
from prefect.environments import RemoteEnvironment

f = Flow("example-env", environment=RemoteEnvironment(executor="prefect.engine.executors.LocalExecutor"))
```

or assign it directly:

```python
from prefect.environments import RemoteEnvironment

f = Flow("example-env")
f.environment = RemoteEnvironment(executor="prefect.engine.executors.LocalExecutor")
```

### Setup & Execute

The two main environment functions are `setup` and `execute`. The `setup` function is responsible for creating or prepping any infrastructure requirements before the flow is executed. This could take the form of functionality such as spinning up a Dask cluster or checking available platform resources. The `execute` function is responsible for actually telling the flow where and how it needs to run. This could take the form of functionality such as running the flow in process, as per the [`RemoteEnvironment`](https://docs.prefect.io/api/unreleased/environments/execution.html##remoteenvironment), or registering a new Fargate task, as per the [`FargateTaskEnvironment`](https://docs.prefect.io/api/unreleased/environments/execution.html#fargatetaskenvironment).

### Environment Callbacks

Each Prefect environment has two optional arugments `on_start` and `on_exit` that function as callbacks which act as extra customizable functionality outside of infrastructure or flow related processes. Users can provide an `on_start` function which will execute before the flow starts in the main process and an `on_exit` function which will execute after the flow finishes.

### Labels

Environments expose a configurable list of `labels` that allow you to label your flows to determine where they get executed. This is in conjunction with the list of `labels` you may provide on your [Prefect Agents](../agent/overview.html).

#### Label Example

Labels work in a way in which the Agent's labels must be a superset of the labels provided on the environment for the flow. This means that if you have a flow's environment labels as `["dev"]` and an Agent with labels set to `["dev", "staging"]` then it will run that flow because the _dev_ label is a subset of the labels provided to the Agent.

```python
from prefect.environments import RemoteEnvironment

f = Flow("example-label")
f.environment = RemoteEnvironment(labels=["dev"])
```

```python
from prefect.agent import LocalAgent

LocalAgent(labels=["dev", "staging"]).start()

# Flow will be picked up by this agent
```

On the other hand if you deploy a flow that has environment labels set to `["dev", "staging"]` and run an Agent with the labels `["dev"]` then it will not pick up the flow because there exists labels in the environment which were not provided to the agent.

```python
from prefect.environments import RemoteEnvironment

f = Flow("example-label")
f.environment = RemoteEnvironment(labels=["dev", "staging"])
```

```python
from prefect.agent import LocalAgent

LocalAgent(labels=["dev"]).start()

# Flow will NOT be picked up by this agent
```

:::tip Empty Labels
An empty label list is effectively considered a label. This means that if you deploy a flow with no environment labels it will only be picked up by Agents which also do not have labels specified.
:::
