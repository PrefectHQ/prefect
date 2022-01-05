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

