# Flow runners

Flow runners are responsible for creating and monitoring infrastructure for flow runs associated with deployments.

A flow runner can only be used with a deployment. When you run a flow directly by calling the flow yourself, you are responsible for the environment in which the flow executes.

## Flow runners overview

Orion uses flow runners to create the infrastructure for a user's flow to execute.

The flow runner is attached to a deployment and is propagated to flow runs created for that deployment. The flow runner is deserialized by the agent and it has two jobs:

- Create infrastructure for the flow run
- Run a Python command to start the `prefect.engine` in the infrastructure, which executes the flow

The engine acquires and calls the flow. The flow runner doesn't know anything about how the flow is stored, it's just passing a flow run id to the engine.

Flow runners are specific to the environments in which flows will run. Prefect currently provides the following flow runners:

- `UniversalFlowRunner` is the base flow runner
- `SubprocessFlowRunner` runs flows in a local subprocess
- `DockerFlowRunner` runs flows in a Docker container

!!! note "What about tasks?" 

    Flows and tasks can both use runners to manage the environment in which code runs. While flows use flow runners, tasks use task runners. For more on how task runners work, see our [documentation on task runners](/concepts/task-runners/).


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

All flow runners have the configuration fields at [`UniversalFlowRunner`](/api-ref/prefect/flow_runners/#prefect.flow_runners.UniversalFlowRunner) available. Additionally, every flow runner has type-specific options.

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

## Using the universal flow runner

By including a flow runner type for your deployment, you are specifying the infrastructure that will run your flow. If you want your flow to be able to run on any infrastructure, deferring the choice to the agent, you may either leave the `flow_runner` field blank or set it to a `UniversalFlowRunner`.

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

## Types of flow runners

The following flow runners are available:

- `UniversalFlowRunner` is the base flow runner
- `SubprocessFlowRunner` runs flows in a local subprocess
- `DockerFlowRunner` runs flows in a Docker container

See the [`prefect.flow_runners` API reference](/api-ref/prefect/flow-runners/) for descriptions of each flow runner.

If a deployment has a universal flow runner or no flow runner specified, the default flow runner will be used.

The default flow runner is configured by the agent. Currently, the agent does not allow the default to be changed. A `SubprocessFlowRunner` will always be used.

Check out the [Docker flow runner tutorial](/tutorials/docker-flow-runner/) for getting started running a flow in a Docker container.

Check out the [virtual environments](/tutorials/virtual-environments/) for getting started running a flow in a Python virtual environment.