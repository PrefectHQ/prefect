---
description: Learn about the Prefect 2.0 and Prefect Cloud UI and dashboard.
tags:
    - Orion
    - UI
    - dashboard
    - Prefect Cloud
---

# Dashboard

The dashboard provides high-level visibility into the status of your flow and task runs. From the dashboard, you can filter results to explore specific run states, scheduled runs, and more. You can drill down into details about: 

- Flows
- Deployments
- Flow runs
- Task runs

When Prefect Server is running, you can access the UI at [http://127.0.0.1:4200](http://127.0.0.1:4200). If you're running a local server or accessing a server running in a container or cluster, the default initial view is the dashboard.

![Prefect Orion UI dashboard.](/img/ui/orion-dashboard.png)

The following sections discuss each section of the dashboard view.

- [Filters](#filters)
- [Run history](#run-history)
- [Details](#details)

## Filters

The Filters area at the top of the dashboard provides controls that enable you to display selected details of flow runs on the dashboard. Filters include flow run state, tags, time, and more. See the [Filters](/ui/filters/) documentation for more information.

![Highlighting the filters section of the dashboard.](/img/ui/orion-dash-filters.png)

## Run history

The Run history area of the dashboard provides an overview of recent flow runs. [Filters](#filters) control the detail of what's shown in the Run history.

![Highlighting the run history section of the dashboard.](/img/ui/orion-dash-history.png)

## Details

The details area of the dashboard provides a listing of:

- Flows the Orion server knows about
- Deployments created with the Orion server
- Flow runs that are scheduled or have attempted to execute
- Task runs created by flows runs

[Filters](#filters) control what's shown in the details section. See the [Flows and Tasks](/ui/flows-and-tasks/) documentation for more information.

![Highlighting the details section of the dashboard.](/img/ui/orion-dash-details.png)