---
description: View and manage flows in the Prefect UI and Prefect Cloud.
tags:
    - Orion
    - UI
    - flows
    - Prefect Cloud
---

# Flows

A [flow](/concepts/flows/) contains the instructions for workflow logic, including the `@flow` and `@task` functions that define the work of your workflow. 

The **Flows** page in the Prefect UI lists any flows that have been observed by a Prefect API. This may be your [Prefect Cloud](/ui/cloud/) workspace API, a local Prefect Orion API server, or the Prefect ephemeral API in your local development environment.

![View a list of flows observed by Prefect in the Prefect UI.](/img/ui/orion-flows.png)

For each flow, the **Flows** page lists the flow name and displays a graph of activity for the flow.

You can see additional details about the flow by [selecting the flow name](#inspect-a-flow). You can see detail about the flow run by [selecting the flow run name](/ui/flow-runs/#inspect-a-flow-run).

## Inspect a flow

If you select the name of a flow on the **Flows** page, the UI displays details about the flow.

![Details for a flow in the Prefect UI](/img/ui/orion-flow-details.png)

If deployments have been created for the flow, you'll see them here. Select the deployment name to see further details about the deployment.

On this page you can also:

- Copy the ID of the flow or delete the flow from the API by using the options button to the right of the flow name. Note that this does not delete your flow code. It only removes any record of the flow from the Prefect API.
- Pause a schedule for a deployment by using the toggle control.
- Copy the ID of the deployment or delete the deployment by using the options button to the right of the deployment.
