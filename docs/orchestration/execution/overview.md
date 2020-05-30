# Execution Overview

Executing flows using the Prefect API is accomplished through two powerful abstractions — storage and environments. By combining these two abstractions, flows can be saved, shared, and executed across various platforms.

[[toc]]

## Storage

[Storage](https://docs.prefect.io/api/latest/environments/storage.html) objects are pieces of functionality which define how and where a Flow should be stored. Prefect supports storage options ranging from ephemeral in-memory storage to Docker images which can be stored in registries.

### How Storage is Used

To attach storage to your Flows, provide your storage object at initialization:

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

When you register your flow with the Prefect API the storage object attached to the flow will be built. At this step the flow is serialized to byte code and placed inside of the storage. For added convenience, `flow.register` will accept arbitrary keyword arguments which will then be passed to the initialization method of your configured default storage class (which is `Local` by default). The following code will actually pass the `registry_url` to the `Docker` Storage object for you at registration-time and push that image to your specified registry:

```python
from prefect import Flow
from prefect.environments.storage import Docker

f = Flow("example-easy-storage")
f.storage = Docker()

# all other init kwargs to `Docker` are accepted here
f.register("My First Project", registry_url="prefecthq/storage-example")
```

::: tip Pre-Build Storage
You are also able to optionally build your storage separate from the `register` command and specify that you do not want to build it again at registration-time:

```python
from prefect.environments.storage import Docker

f = Flow("example-storage")
f.storage = Docker(registry_url="prefecthq/storage-example")

# Pre-build storage
f.storage.build()

# Register but don't rebuild storage
f.register("My First Project", build=False)
```

:::

## Environments

While Storage objects provide a way to save and retrieve Flows, [Environments](https://docs.prefect.io/api/latest/environments/execution.html) specify _how your Flow should be run_ e.g., which executor to and whether there are any auxiliary infrastructure requirements for your Flow's execution. For example, if you want to run your Flow on Kubernetes using an auto-scaling Dask cluster then you're going to want to use an environment for that!

### How Environments are Used

By default, Prefect attaches `RemoteEnvironment` with your local default executor to every Flow you create. To specify a different environment, provide it to your Flow at initialization:

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

The two main environment functions are `setup` and `execute`. The `setup` function is responsible for creating or prepping any infrastructure requirements before the Flow is executed e.g., spinning up a Dask cluster or checking available platform resources. The `execute` function is responsible for actually telling the Flow where and how it needs to run e.g., running the Flow in process, as per the [`RemoteEnvironment`](https://docs.prefect.io/api/latest/environments/execution.html##remoteenvironment), or registering a new Fargate task, as per the [`FargateTaskEnvironment`](https://docs.prefect.io/api/latest/environments/execution.html#fargatetaskenvironment).

### Environment Callbacks

Each Prefect environment has two optional arguments - `on_start` and `on_exit` - which can be used to add functionality outside of infrastructure or Flow-related processes. The `on_start` callback is executed before the Flow starts in the main process; the `on_exit` callback is executed after the Flow finishes.

_For more information on the design behind Environment Callbacks visit [PIN 12](/core/PINs/PIN-12-Environment-Callbacks.html)._

#### Callback Example

In this example we have a function called `report_cluster_metrics` which, when run on a Kubernetes cluster, gathers information about current resource usage. We can use this to track resource usage both before and after a Flow run.

```python
from prefect import Flow, task
from prefect.environments import RemoteEnvironment


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
environment = RemoteEnvironment(on_start=report_cluster_metrics,
                                on_exit=report_cluster_metrics)


with Flow("Callback-Example", environment=environment) as flow:
    e = extract()
    t = transform(e)
    l = load(t)
```

### Labels

Environments expose a configurable list of `labels`, allowing you to label your Flows and determine where they are executed. This works in conjunction with the list of `labels` you may provide on your [Prefect Agents](../agents/overview.html#flow-affinity:-labels), as well as the [Flow Concurrency Limits](#limiting-flow-run-execution).

#### Agent Label Example

An Agent's labels must be a superset of the labels specified on a Flow's environment. This means that if a Flow's environment labels are specified as `["dev"]` and an Agent is running with labels set to `["dev", "staging"]`, the agent will run that Flow because the _dev_ label is a subset of the labels provided to the Agent.

```python
from prefect.environments import RemoteEnvironment

f = Flow("example-label")
f.environment = RemoteEnvironment(labels=["dev"])
```

```python
from prefect.agent.local import LocalAgent

LocalAgent(labels=["dev", "staging"]).start()

# Flow will be picked up by this agent
```

On the other hand if you register a flow that has environment labels set to `["dev", "staging"]` and run an Agent with the labels `["dev"]` then it will not pick up the flow because there exists labels in the environment which were not provided to the agent.

```python
from prefect.environments import RemoteEnvironment

f = Flow("example-label")
f.environment = RemoteEnvironment(labels=["dev", "staging"])
```

```python
from prefect.agent.local import LocalAgent

LocalAgent(labels=["dev"]).start()

# Flow will NOT be picked up by this agent
```

:::tip Empty Labels
An empty label list is effectively considered a label. This means that if you register a flow with no environment labels it will only be picked up by Agents which also do not have labels specified.
:::

### Limiting Flow Run Execution
While managing your infrastructure that run your flows, you may run into an issue where too many flows are trying to be run at once. To help mitigate this occuring, you can choose to limit the number of conccurent flows running in an environment based on its `labels`. Each flow run in the `Running` state occupies one slot of concurrency in that `environment`. If an `environment` has multiple `labels` with multiple concurrency limits, there must be at least one slot available per concurrency limit. By default, any `label` that isn't explicitely given a concurrency limit allows an unlimited number of flows to be `Running` at any given time.

#### Creating Flow Concurrency Limits
To create a `Flow Concurrency Limit`, the only current supported method of doing so is from the GraphQL API. Creating one can be done by executing the following mutation:

```graphql
mutation {
  update_flow_concurrency_limit(input: { name: "my env label", limit: 5 }) {
    id
  }
}
```

The mutation `update_flow_concurrency_limit` will update that limit if it already exists or will create a new concurrency limit for you if one with that name does not exist.

#### Behavior
Limiting the number of flow runs in an environment is an opt-in feature. By default, if an environment has no labels, or there aren't set concurrency limits for those labels, it allows an unlimited number of flow runs. In order for a flow run to start `Running` in an environment, all labels on that environment must either have concurrency slots available or not have concurrency limits set. If an environment has multiple labels with varying concurrency limits, the flows running in that environment are limited by the strictest combination of concurrency limits.

#### Flow Concurrency Limiting Example
Assuming you issue the following mutations to create concurrency limits, the expected behavior is that any `Environment` tagged with `"prod"` will have at most 10 flows running, while `"dev"` has at most 5. If any environment is tagged as both, the limiting takes the stricter of the two, only allowing 5 flows to run at once.

```graphql
mutation {
  update_flow_concurrency_limit(input: { name: "prod", limit: 10 }) {
    id
  }
}

mutation {
  update_flow_concurrency_limit(input: { name: "dev", limit: 5 }) {
    id
  }
}
```


Since the flows below are both tagged as `["dev"]`, the environment in which they execute will at most have 5 flow runs running at once.
```python
from prefect import Flow
from prefect.environments import RemoteEnvironment

first_dev_flow = Flow("concurrency-limited-example", environment=RemoteEnvironment(labels=["dev"]))
second_dev_flow = Flow("other-limited-example", environment=RemoteEnvironment(labels=["dev"]))
```

The flow has one label, `"reporting"`, that does not have a concurrency limit associated with it. In this case, this label is ignored for the purposes of concurrency checks, and only is limited by the capacity of `"prod"`.
```python
from prefect import Flow
from prefect.environments import RemoteEnvironment

prod_flow = Flow("concurrency-limited-prod-example", environment=RemoteEnvironment(labels=["prod", "reporting"]))
```