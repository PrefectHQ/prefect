# Flow runners

Flow runners are responsible for creating and monitoring infrastructure for flow runs associated with deployments.

When creating ad hoc flow runs by calling a flow yourself, you are taking full control of your flow's execution environment. A flow runner cannot be used in this case.

## Flow runners overview

There are parallels between flow and task runs. Notably, each has a step where infrastructure can be created for the user's code to execute in. 

The flow runner is attached to a deployment and is propagated to flow runs created for that deployment. The flow runner is deserialized by the agent and it has two jobs:

- Create infrastructure
- Run a Python command to start the `prefect.engine` in the infrastructure

The engine acquires and calls the flow. The flow runner doesn't know anything about how the flow is stored, it's just passing a flow run id to the engine.

Flow runners are specific to the environments in which flows will run. Prefect currently provides the following flow runners:

- `UniversalFlowRunner` is the base flow runner
- `SubprocessFlowRunner` runs flows in a local subprocess
- `DockerFlowRunner` runs flows in a Docker container

## Using a flow runner

To use a specific flow runner, import the flow runner from `prefect.flow_runners` and assign the flow runner to the deployment in the deployment specification when a deployment is created. 

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

## Configuring a flow runner

All flow runners have the configuration fields at [`UniversalFlowRunner`](/api-ref/prefect/flow_runners/#prefect.flow_runners.UniversalFlowRunner) available. Additionally, every flow runner has type-specific options.

For example, you can configure the `SubprocessFlowRunner` to include an environment variable (a universal setting) and an Anaconda environment (a subprocess-specific setting):

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

## Using the universal flow runner

By including a flow runner type for your deployment, you are specifying where your flow will run. If you want your flow to be able to run on any infrastructure, deferring the choice to the agent, you may either leave the `flow_runner` field blank or set it to a `UniversalFlowRunner`.

The `UniversalFlowRunner` is useful when you want to use the universal settings without limiting the flow run to a specific type of infrastructure.

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

## Configuring the default flow runner

If a deployment has a universal flow runner or no flow runner specified, the default flow runner will be used.

The default flow runner is configured by the agent. Currently, the agent does not allow the default to be changed. A `SubprocessFlowRunner` will always be used.

## Types of flow runners

The following flow runners are available:

- `UniversalFlowRunner` is the base flow runner
- `SubprocessFlowRunner` runs flows in a local subprocess
- `DockerFlowRunner` runs flows in a Docker container
- `KubernetesFlowrunner` (planned for a future release)

See the [`prefect.flow_runners` API reference](/api-ref/prefect/flow-runners/) for descriptions of each flow runner.

Check out the [Docker flow runner tutorial](/tutorials/docker-flow-runner/) for getting started running a flow in a Docker container.

Check out the [virtual environments](/tutorials/virtual-environments/) for getting started running a flow in a Python virtual environment.

## Flow runner serialization

When a deployment is created, the flow runner must be serialized and stored by the API. When serialized, a flow runner is converted to a `FlowRunnerSettings` type. You'll see this schema when interacting with the API.

When an agent begins submission of a flow run, it pulls flow runner settings from the API. The settings are deserialized into a concrete `FlowRunner` instance, which is used to create the infrastructure for the flow run.
