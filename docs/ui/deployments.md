---
description: Manage flow deployments from the Prefect UI and Prefect Cloud.
tags:
    - Orion
    - UI
    - deployments
    - flow runs
    - schedules
    - parameters
    - Prefect Cloud
---

# Deployments

[Deployments](/concepts/deployments/) encapsulates instructions for running a flow, allowing it to be scheduled and triggered via API. 

The **Deployments** page in the UI displays any deployments that have been created on the current API instance or Prefect Cloud workspace.

![Viewing deployments in the Prefect UI](/img/ui/orion-deployments.png)

Selecting the toggle next to a deployment pauses the run schedule for the deployment, if the deployment specifies a schedule. 

The button next to the pause toggle provides commands to copy the deployment ID or delete the deployment. Note that deleting the deployment only removes the deployment object from the API, along with any of its scheduled flow runs. It does not affect the source files for your flow or deployment specification.

Selecting a flow name displays details about the flow. See [Flows and Tasks](/ui/flows-and-tasks/) for more information.

Selecting a deployment name displays details about the deployment. The **Overview** tab displays general details of the deployment.

![Viewing details of a deployment in the Prefect UI](/img/ui/orion-deployment-details.png)

Selecting the **Run** button starts an ad-hoc flow run for the deployment.

Selecting the toggle next to a deployment pauses the run schedule for the deployment, if the deployment specifies a schedule. 

The button next to the toggle provides commands to copy the deployment ID or delete the deployment.

The **Parameters** tab displays any parameters specified for the deployment.

![Viewing parameters of a deployment in the Prefect UI](/img/ui/orion-deployment-params.png)

!!! note "Editing deployments"
    You may edit or update an existing deployment within the Prefect UI or via the CLI by applying changes from an edited deployment YAML file. 
    
    To change a deployment via the CLI, edit the deployment YAML file, then use the `prefect deployment apply` CLI command. If a deployment already exists, it will be updated rather than creating a new deployment. See the [Deployments](/concepts/deployments/) documentation for details.