---
description: Prefect flow runners are responsible for creating and monitoring the infrastructure for flow runs associated with deployments.
tags:
    - orchestration
    - flow runners
    - KubernetesFlowRunner
    - DockerFlowRunner
    - SubprocessFlowRunner
    - Kubernetes
    - Docker
---

# Flow runners

[Flow runners](/api-ref/prefect/flow-runners/) are responsible for creating and monitoring infrastructure for flow runs associated with deployments.

A flow runner can only be used with a [deployment](/concepts/deployments/). When you run a flow directly by calling the flow yourself, you are responsible for the environment in which the flow executes.

## Flow runners overview

Orion uses flow runners to create the infrastructure for a user's flow to execute.

The flow runner is attached to a deployment and is propagated to flow runs created for that deployment. The flow runner is deserialized by the agent and it has two jobs:

- Create infrastructure for the flow run
- Run a Python command to start the `prefect.engine` in the infrastructure, which executes the flow

The engine acquires and calls the flow. The flow runner doesn't know anything about how the flow is stored, it's just passing a flow run id to the engine.

Flow runners are specific to the environments in which flows will run. Prefect currently provides the following flow runners:

- [`UniversalFlowRunner`](/api-ref/prefect/flow-runners/#prefect.flow_runners.UniversalFlowRunner) contains configuration options used by other flow runners. You should not use this flow runner directly.
- [`SubprocessFlowRunner`](/api-ref/prefect/flow-runners/#prefect.flow_runners.SubprocessFlowRunner) runs flows in a local subprocess.
- [`DockerFlowRunner`](/api-ref/prefect/flow-runners/#prefect.flow_runners.DockerFlowRunner) runs flows in a Docker container.
- [`KubernetesFlowRunner`](/api-ref/prefect/flow-runners/#prefect.flow_runners.KubernetesFlowRunner) runs flows in a Kubernetes Job.

Check out the [virtual environments](/tutorials/virtual-environments/) for getting started running a flow in a Python virtual environment.


!!! note "What about tasks?" 

    Flows and tasks can both use runners to manage the environment in which code runs. While flows use flow runners, tasks use task runners. For more on how task runners work, see [Task Runners](/concepts/task-runners/).


## Using a flow runner

To use a flow runner, pass an instance of the desired flow runner type into a deployment specification. 

For example, when using a `DeploymentSpec`, you can attach a `SubprocessFlowRunner` to indicate that this flow should be run in a local subprocess:

```python
from prefect import flow
from prefect.deployments import DeploymentSpec
from prefect.flow_runners import SubprocessFlowRunner

@flow
def my_flow():
    pass

DeploymentSpec(
    name="test",
    flow=my_flow,
    flow_runner=SubprocessFlowRunner(),
)
```

Next, use this deployment specification to create a deployment with the `prefect deployment create` command. Assuming the code exists in a deployment.py file, the command looks like this:

```bash
prefect deployment create ./deployment.py
```

Once the deployment exists, any flow runs that this deployment starts will use `SubprocessFlowRunner`.

## Configuring a flow runner

All flow runners have the configuration fields at [`UniversalFlowRunner`](/api-ref/prefect/flow-runners/#prefect.flow_runners.UniversalFlowRunner) available. Additionally, every flow runner has type-specific options.

You can mix type-specific flow runner options with universal flow runner options. For example, you can configure the `SubprocessFlowRunner` to include an environment variable (a universal setting) and an Anaconda environment (a subprocess-specific setting):

```python hl_lines="12"
from prefect import flow
from prefect.deployments import DeploymentSpec
from prefect.flow_runners import SubprocessFlowRunner

@flow
def my_flow():
    pass

DeploymentSpec(
    name="test",
    flow=my_flow,
    flow_runner=SubprocessFlowRunner(env={"MY_VARIABLE": "FOO"}, condaenv="test"),
)
```

## Universal flow runner

By including a flow runner type for your deployment, you are specifying the infrastructure that will run your flow. If you want your flow to be able to run on any infrastructure, deferring the choice to the agent, you may either leave the `flow_runner` field blank or set it to a [`UniversalFlowRunner`](/api-ref/prefect/flow-runners/#prefect.flow_runners.UniversalFlowRunner).

If a deployment has a `UniversalFlowRunner` or no flow runner specified, the default flow runner will be used.

The `UniversalFlowRunner` is useful when you want to use the universal settings without limiting the flow run to a specific type of infrastructure.

`UniversalFlowRunner` supports the following settings:

| Attributes | Description |
| ---- | ---- |
| env | String containing environment variables to provide to the flow run. |

For example, you can specify environment variables that will be provided no matter what infrastructure the flow runs on:

```python hl_lines="12"
from prefect import flow
from prefect.deployments import DeploymentSpec
from prefect.flow_runners import UniversalFlowRunner

@flow
def my_flow():
    pass

DeploymentSpec(
    name="test",
    flow=my_flow,
    flow_runner=UniversalFlowRunner(env={"MY_VARIABLE": "FOO"}),
)
```

## Subprocess flow runner

[`SubprocessFlowRunner`](/api-ref/prefect/flow-runners/#prefect.flow_runners.SubprocessFlowRunner) executes flow runs in a local subprocess.

`SubprocessFlowRunner` supports the following settings:

| Attributes | Description |
| ---- | ---- |
| stream_output | Bool indicating whether to stream output from the subprocess to local standard output. |
| condaenv | The name of an anaconda environment to run the flow in. A path can be provided instead, similar to `conda --prefix ...`. |
| virtualenv | The path to a virtualenv environment to run the flow in. This also supports Python built-in `venv` environments. |

## Docker flow runner

[`DockerFlowRunner`](/api-ref/prefect/flow-runners/#prefect.flow_runners.DockerFlowRunner) executes flow runs in a container.

Requirements for `DockerFlowRunner`:

- Docker Engine must be available.
- You must configure remote [Storage](/concepts/storage/) such as S3, Google Cloud Storage, or Azure Blob Storage. Local storage configuration such as Local Storage or Temporary Local Storage are not supported for Docker.
- The API must be available from within the flow run container. To facilitate connections to locally hosted APIs, `localhost` and `127.0.0.1` will be replaced with `host.docker.internal`.

`DockerFlowRunner` supports the following settings:

| Attributes | Description |
| ---- | ---- |
| image | An optional string specifying the tag of a Docker image to use. |
| networks | An optional list of strings specifying Docker networks to connect the container to. |
| labels | An optional dictionary of labels, mapping name to value. |
| auto_remove | Bool indicating whether the container will be removed on completion. If False, the container will remain after exit for inspection. |
| volumes | An optional list of volume mount strings in the format of "local_path:container_path". |
| stream_output | Bool indicating whether to stream output from the subprocess to local standard output. |

Prefect automatically sets a Docker image matching the Python and Prefect version you're using at deployment time. You can see all available images at [Docker Hub](https://hub.docker.com/r/prefecthq/prefect/tags?page=1&name=2.0).

Check out the [Docker flow runner tutorial](/tutorials/docker-flow-runner/) for getting started running a flow in a Docker container.

### Configuring a custom image

When you create a deployment with a Docker flow runner, the container image defaults to a Prefect image. This image has the `prefect` package preinstalled.

We ensure that the Prefect and Python versions used to create the deployment are used when the deployment is run. For example, if using Prefect `2.0a13` and Python `3.8`, we will generate the image tag `prefecthq/prefect:2.0a13-python3.8`.

Often, you will want to use your own Docker image to run your flow. This image may have additional requirements preinstalled.

To use a custom image, provide the `image` setting:

```python
DockerFlowRunner(image="my-custom-tag")
```

When using a custom image, you must have the `prefect` Python package installed and available from the default `python` command. We recommend deriving your image from a Prefect base image available from [Docker Hub](https://hub.docker.com/r/prefecthq/prefect/tags?page=1&name=2.0).

### Adding requirements to the default image

If you have some Python dependencies, but do not want to build your own image, the default Prefect image supports dynamic installation with `pip`. To use this feature, provide the environment variable `EXTRA_PIP_PACKAGES` as a space-delimited string:

```python
DockerFlowRunner(env={"EXTRA_PIP_PACKAGES": "my-extra-package1 my-extra-package2"})
```

## Kubernetes flow runner

[`KubernetesFlowRunner`](/api-ref/prefect/flow-runners/#prefect.flow_runners.KubernetesFlowRunner) executes flow runs in a Kubernetes Job.

Requirements for `KubernetesFlowRunner`:

- `kubectl` must be available.
- You must configure remote [Storage](/concepts/storage/) such as S3, Google Cloud Storage, or Azure Blob Storage. Local storage configuration such as Local Storage or Temporary Local Storage are not supported for Kubernetes.

The Prefect CLI command `prefect orion kubernetes-manifest` automatically generates a Kubernetes manifest with default settings for Prefect deployments. By default, it simply prints out the YAML configuration for a manifest. You can pipe this output to a file of your choice and edit as necessary.

`KubernetesFlowRunner` supports the following settings:

| Attributes | Description                                                                                                            |
| ---- |------------------------------------------------------------------------------------------------------------------------|
| image | String specifying the tag of a Docker image to use for the Job.                                                        |
| namespace | String signifying the Kubernetes namespace to use.                                                                     |
| labels | Dictionary of labels to add to the Job.                                                                                |
| image_pull_policy | The Kubernetes image pull policy to use for Job containers.                                                            |
| restart_policy | The Kubernetes restart policy to use for Jobs.                                                                         |
| stream_output | Bool indicating whether to stream output from the subprocess to local standard output.                                 |
| node_selector | Dict that indicates where to start the pod   ```KubernetesFlowRunner(node_selector={"hcloud/node-group": "CPX11"})``` |

Check out the [Kubernetes flow runner tutorial](/tutorials/kubernetes-flow-runner/) for an example of running deployments as Jobs with Kubernetes.
