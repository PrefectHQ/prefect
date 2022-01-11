# Flow runners

Flow runners are responsible for running Prefect flows. Each deployment has a flow runner associated with it. The flow runner is used to create and monitor infrastructure for flow runs associated with deployments.

When creating adhoc flow runs by calling a flow yourself, you are taking full control of your flow's execution environment. A flow runner cannot be used in this case.

## Using an flow runner

Import flow runners from `prefect.flow_runners` and assign one when the deployment is created. 

For example, when using a `DeploymentSpec`, we can attach a `SubprocessFlowRunner` to indicate that this flow should be run in a subprocess:

```python hl_lines="13"
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

All flow runners have the configuration fields at [UniversalFlowRunner](...) available. Additionally, each flow runner has type specific options.

For example, we can configure our subprocess flow runner to include an environment variable (a universal setting) and an Anaconda environment (a subprocess specific setting):

```python hl_lines="13"
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

For example, you can specify environment variables which will be provided no matter what infrastructure the flow runs on:

```python hl_lines="13"
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

- Universal
- Subprocess
- Docker
- Kubernetes (planned)

See the [`prefect.flow_runners` API reference](/api-ref/prefect/flow-runners/) for descriptions of each flow runner.

Check out the [Docker flow runner tutorial](/tutorials/docker-flow-runner/) for getting started running a flow in a Docker container.


## Flow runner serialization

When a deployment is created, the flow runner must be serialized and stored by the API. When serialized, a flow runner is converted to a `FlowRunnerSettings` type. You'll see this schema when interacting with the API.

When an agent begins submission of a flow run, it pulls flow runner settings from the API. The settings are deserialized into a concrete `FlowRunner` instance which is used to create the infrastructure for the flow run.
