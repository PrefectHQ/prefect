---
sidebarDepth: 0
---

# Prefect Cloud: The Basics

Welcome to Prefect Cloud! Now that you have an account, this guide will help you orient yourself and understand the minor adjustments required to deploy your Flows to Cloud.

## Prefect Agent

Before you can deploy Prefect flows from Prefect Cloud you must stand up a Prefect Agent on your desired platform. For more agent documentation visit the [Agent](agent/overview.html) section of the Cloud docs.

## Create a Project

Before you can interact with Prefect Cloud you need to be able to authenticate with Prefect Cloud's API. To do so, visit the Cloud UI and retrieve an Authorization Token from the upper right hand corner menu. Either follow the instructions from the UI, or use [Prefect's CLI](https://docs.prefect.io/core/concepts/cli.html#auth) to persist your token locally.

Prior to deploying your first Flow you should create a Project in Prefect Cloud. Recall that Projects are simply an organizational tool for your Flows, and can be thought of as a directory structure.

There are two simple ways of creating projects, depending on your personal preference:

**Python**

```python
from prefect import Client

c = Client()
c.create_project(project_name="My Project")
```

**GraphQL**

```graphql
mutation {
  createProject(input: { name: "My Project" }) {
    project {
      id
      name
    }
  }
}
```

## Deployment

To deploy your Flow to Cloud requires that you have [Docker](https://www.docker.com/) running locally and that you have have access to a Docker registry that you are comfortable pushing your code to. Additionally, note that your Prefect Agent (which runs within your infrastructure and _not_ within Prefect Cloud) will require access to this registry as well.

Now that you have Docker running and have your Prefect Cloud auth token ready, there are two small changes to your Flow that are required prior to deployment: specifying an _execution environment_ and your _Docker storage metadata_.

### Execution Environments

[Prefect execution environments](https://docs.prefect.io/api/unreleased/environments/execution.html) specify execution information about _how your Flow should be run_. For example, what executor should be used and are there any auxiliary infrastructure requirements for your Flow's execution? At this exact moment, the only supported execution environment is the [Remote Environment](https://docs.prefect.io/api/unreleased/environments/execution.html#remoteenvironment) which allows you to specify which Prefect Executor to use, but this will soon expand into a richer library.

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

### Storage

The [Prefect Storage interface](https://docs.prefect.io/api/unreleased/environments/storage.html#docker) provides a way to specify (via metadata) _where_ your Flow code is actually stored. Currently the only supported Storage class in Prefect Cloud is [Docker storage](https://docs.prefect.io/api/unreleased/environments/storage.html#docker). The only _required_ piece of information to include when creating your Docker storage class is the `registry_url` of the Docker registry where your image will live. All other keyword arguments are optional and "smart" defaults will be inferred.

Similar to environments above, simply provide your storage at initialization:

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

For added convenience, `flow.deploy` will accept arbitrary keyword arguments which will then be passed to the initialization method of your configured default storage class (which is `Docker` by default). Consequently, the following code will actually create a `Docker` object for you at deploy-time:

```python
from prefect import Flow

f = Flow("example-easy-storage")

# all other init kwargs to `Docker` are accepted here
f.deploy("My First Project", registry_url="prefecthq/storage-example")
```

::: warning Serialization
A common issue when first onboarding to Cloud is understanding how Flow serialization into your Docker image works. Two common issues are:

- ensuring all Python package dependences are provided (this is usually fixed via a judicious choice of `base_image` or the `python_dependencies` kwarg)
- ensuring all utility functions / scripts are importable at runtime via the same Python path (this usually requires understanding [`cloudpickle`](https://github.com/cloudpipe/cloudpickle) a little deeper)

A tutorial on how to debug such issues can be found [here](https://docs.prefect.io/core/tutorials/local-debugging.html#locally-check-your-flow-s-docker-storage).
:::

### `flow.deploy`

Now that your Flow has all the required attributes, it's time to deploy to Cloud! All that you have to do now is:

```python
flow.deploy(project_name="My Prefect Cloud Project Name")
```

[This convenience method](https://docs.prefect.io/api/unreleased/core/flow.html#prefect-core-flow-flow-deploy) will proceed to build your Docker image, layer Prefect on top, serialize your Flow into the image, perform a "health check" that your Flow can be properly deserialized within the image and finally push the image to your registry of choice. It will then send the corresponding _metadata_ to Prefect Cloud. As above, note that `flow.deploy` also accepts initialization keyword arguments for `Docker` storage if you want to avoid creating that object yourself.

::: tip GraphQL
Advanced users who manually build their own images and perform their own serialization can actually deploy Flows via pure GraphQL (assuming they have pushed their image already). Most people will never do this, but it highlights the minimal amount of information that Cloud requires to function. Using our storage example above, the corresponding GraphQL call is simply:

```graphql
mutation($input: createFlowInput!) {
  createFlow(input: $input) {
    id
  }
}
```

where `$input` is:

```python
{"name": "example-env",
 "type": "prefect.core.flow.Flow",
 "schedule": null,
 "parameters": [],
 "tasks": [],
 "edges": [],
 "reference_tasks": [],
 "environment": {"executor_kwargs": {},
  "executor": "prefect.engine.executors.LocalExecutor",
  "__version__": "0.6.1",
  "type": "RemoteEnvironment"},
 "__version__": "0.6.1",
 "storage": {"image_tag": "latest",
  "flows": {"storage-example": "/root/.prefect/storage-example.prefect"},
  "registry_url": "prefecthq/storage-example",
  "image_name": "storage-example",
  "prefect_version": "0.6.1",
  "__version__": "0.6.1",
  "type": "Docker"}}
```

which you may recognize as the output of `f.serialize()`
:::

Congratulations, you have now deployed your first Flow!
