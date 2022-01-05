# Deployments

A deployment is a configuration object that enables triggering an Orion flow via API. 

Deployments include metadata such as flow and deployment name, flow location, and tags, and may also specify parameters and schedules. FlowRunner configuration, if needed, is declared in a deployment.

For detailed information about deployment objects, see the [prefect.deployments](/api-ref/prefect/deployments/) API documentation.

## Deployments overview

In Orion, all local flow runs are tracked by the API, even if you are not actively running a local server. The API does not require prior registration of flows. 

However, if you want a flow run to be managed by an agent and the Orion backend, you must register a deployment for the flow. The deployment is where configuration for the flow run and any necessary infrastructure is defined. 

You can think of a deployment as configuration for managing flows whether run via the CLI or the API and backend.

In addition, a flow can have multiple defined deployments. This enables you to run a single flow with different parameters, on multiple schedules, with different FlowRunners or environment variables. 

A simple example of a deployment specification looks like this:

```python
from prefect.deployments import DeploymentSpec

DeploymentSpec(
    flow_location="flow.py",
    name="flow-deployment", 
)
```

Once the deployment has been registered, you'll see it in the Orion dashboard.

![Screenshot showing deployments listed in the Orion UI.](/img/concepts/deployments.png)

When you run a registered deployment in Orion, the following happens:

- The user runs a deployment, which creates a flow run. (The API runs the deployment for scheduled deployments.)
- An agent detects the flow run and creates infrastructure for the flow run.
- The flow run executes within the flow run infrastructure.

To create a deployment:

- Define the deployment specification
- Register the deployment with the Orion server

## Deployment specification

A deployment specification is an instance of the Prefect [`DeploymentSpec`](/api-ref/prefect/deployments/#prefect.deployments.DeploymentSpec) object.

`DeploymentSpec` takes the following parameters:

| Parameter | Description |
| --------- | ----------- |
| `name` | String specifying the name of the deployment. (Required.) |
| `flow` | The flow object to associate with the deployment. |
| `flow_name` | String specifying the name of the flow to deploy. Only required if loading the flow from a `flow_location` with multiple flows. Inferred from `flow` if provided. |
| `flow_location` | String specifying the path to a script containing the flow to deploy. Inferred from `flow` if provided. (Required if the deployment references a flow in a different file.) |
| `push_to_server` | Boolean indicating whether the flow text will be loaded from the flow location and stored on the server instead of locally. This allows the flow to be compatible with all flow runners. If False, only an agent on the same machine will be able to run the deployment. Default is True. |
| `parameters` | Dictionary of default parameters to set on flow runs from this deployment. If defined in Python, the values should be Pydantic-compatible objects. |
| `schedule` | [Schedule](/concepts/schedules/) instance specifying a schedule for running the deployment. |
| `tags` | List containing tags to assign to the deployment. |

The `flow` object or `flow_location` must be provided. If a `flow` object is not provided, `load_flow` must be called to load the flow from the given flow location.

You can create a deployment specification in two ways:

- In the Python file containing the flow definition.
- In a separate Python file containing only the deployment specification.

If you define the `DeploymentSpec` within the file that contains the flow, you only need to specify the flow function and the deployment name. Other parameters are optional.

```Python
from prefect import flow

@flow
def hello_world(name="world"):
    print(f"Hello {name}!")

# Note: a deployment does not need a command to explicitly
# run the flow. The API handles this for you.
# hello_world()

from prefect.deployments import DeploymentSpec

DeploymentSpec(
    flow=hello_world,
    name="hello-world-daily",
)
```

If you define the `DeploymentSpec` in a separate Python deployment file, specify the path and filename of the file containing the flow definition, along with the deployment name. Other parameters are optional.

```Python
from prefect.deployments import DeploymentSpec

DeploymentSpec(
    flow_location="/path/to/flow.py",
    name="hello-world-daily", 
)
```

A deployment file or flow definition may include multiple `DeploymentSpec` instances, each representing a different deployment specification for the flow. Each `DeploymentSpec` for a given flow must have a unique `name` value. 

## Deployment registration

Registering an Orion deployment enables you to run the deployment &mdash; and its referenced flow &mdash; via API, either on a predefined schedule, or by manually executing the deployment.

Register a deployment with the Prefect CLI using the `prefect deployment create` command, specifying the name of the file containing the deployment specification. You can also run `prefect deployment create` to update an already registered deployment:

```bash
$ prefect deployment create <filename>
```

For example, if the hello-world deployment specification shown above is in the file flow.py, you'd see something like the following:

```bash
$ prefect deployment create flow.py
Loading deployments from python script at 'flow.py'...
Created deployment 'hello-world-daily' for flow 'hello-world'
```

If you define deployment specifications in a file separate from your flow definition, we recommend as a best practice naming your deployment specification file using the model <flowname>_deployment.py. Following the examples shown earlier, for flow.py, you might name the deployment specification flow_deployment.py.

The `prefect deployment` CLI command provides additional commands for managing and running deployments.

| Command | Description |
| ------- | ----------- |
| `create` | Create or update a deployment from a file. |
| `execute` | Execute a local flow run for the given deployment. |
| `inspect` | View details about a deployment. |
| `ls` | View all deployments or deployments for specific flows. |

## Examples

