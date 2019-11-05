# Dask Kubernetes Environment

[[toc]]

## Overview

The Dask Kubernetes Environment is an environment that uses the [dask-kubernetes]() library for dynamically spawning Dask clusters on Kubernetes. This environment is intended for use in cases where users do not want to have a static, long-standing Dask cluster and instead opt for having one temporarily created for each Flow run. The Dask Kubernetes Environment has a few low-configuration options to quickly get up and running however it also provides the ability to specify completely custom [Pod]() specifications for the Dask scheduler and workers.

For more information on the Dask Kubernetes Environment visit the relevant [API documentation](/api/unreleased/environments/execution.html#daskkubernetesenvironment).

## Process

#### Initialization

**Quick Configuration:**

The `DaskKubernetesEnvironment` can optionally accept two worker dependent arguments `min_workers` and `max_workers`. These options set the amount of minimum and maximum workers you want to dynamically scale to for your Dask cluster—defaulting to 1 and 2 respectively.

:::tip Auto Scaling
If you do not want your Dask cluster to automatically scale the amount of workers between the bounds of `min_workers` and `max_workers` then set the two options to the same value.
:::

If you are deploying your flows to a private container registry then you will want to set the `private_registry` kwarg to `True`—defaults to false. You will also want to provide the name of a Prefect Secret to the `docker_secret` kwarg—defaults to _DOCKER_REGISTRY_CREDENTIALS_. This secret should be a dictionary containing the following keys: `"docker-server"`, `"docker-username"`, `"docker-password"`, and `"docker-email"`. This is needed because the relevant Kubernetes `imagePullSecret` will be automatically created if it does not already exist.

For more information on setting Prefect Secrets go [here]().

**Custom Configuration:**

The `DaskKubernetesEnvironment` also has two optional arguments for loading completely custom scheduler and worker YAML specifications—`scheduler_spec_file` and `worker_spec_file`. These options should be file paths to YAML files containing the spec. On initialization these files will be loaded and stored on the environment. It will never be sent to Prefect Cloud and will only exist inside your Flow's Docker storage. You may choose to specify only one of these files as both are not required. It is a common use case for users to only specify a `worker_spec_file` because when using Dask all execution takes place on the workers.

Providing custom YAML configuration is useful in a lot of cases, especially when you may want to control resource usage, node allocation, RBAC, etc...

:::warning YAML Override
If you choose to provide any custom YAML spec files they will take precedence over the quick configuration arguments when creating the Dask cluster.
:::

:::warning Image
When using the custom YAML spec files you must make sure that the `image` is the same image name and tag that was built for your Flow on deployment.

e.g. If you push a Flow's storage as `gcr.io/dev/etl-flow:0.1.0` then your custom YAML spec must contain `- image: gcr.io/dev/etl-flow:0.1.0`
:::

#### Setup

The Dask Kubernetes Environment setup step is responsible for checking the existence of a [Kubernetes Secret]() for a provided `docker_secret` only if `private_registry=True`. If the secret is not found then it will attempt to create one based off of the value set in the Prefect Secret matching the name specified for `docker_secret`.

#### Execute

Create a new [Kubernetes Job]() with the configuration provided at initialization of this environment. That Job is responsible for creating a `KubeCluster` object from the `dask_kubernetes` library with the provided configuration. This is where the min/max workers or custom worker YAML comes into play because `dask_kubernetes` will take care of automatic worker creation based on this specification.

After the Dask cluster has been created the Flow will be run using the [Dask Executor]() pointing to the newly created Dask cluster. All Task execution will take place on the Dask worker pods.

## Examples

#### Dask Kubernetes Environment w/ Min & Max Workers

```python
```

#### Dask Kubernetes Environment w/ Custom Worker YAML

```python
```

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
