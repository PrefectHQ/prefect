---
description: Learn about the Prefect 2.0 and Prefect Cloud UI and dashboard.
tags:
    - Orion
    - UI
    - dashboard
    - Prefect Cloud
---

# Flow Runs

The **Flow Runs** page provides high-level visibility into the status of your flow and task runs. From the dashboard, you can filter results to explore specific run states, scheduled runs, and more. You can drill down into details about: 

- Flows
- Deployments
- Flow runs

When a Prefect API server is running, you can access the UI at [http://127.0.0.1:4200](http://127.0.0.1:4200). If you're running a local server or accessing a server running in a container or cluster, the default initial view is the dashboard.

![Prefect UI dashboard.](/img/ui/orion-dashboard.png)

The following sections discuss each section of the dashboard view.

- [Filters](#filters)
- [Run history](#run-history)
- [Details](#details)

## Filters

The **Filters** area at the top of the page provides controls that enable you to display selected details of flow runs on the dashboard. Filters include date intervals, flow run state, flow name, deployment name, and tags. 

![Highlighting the filters section of the dashboard.](/img/ui/orion-dash-filters.png)

## Run history

The **run history** area of the dashboard provides an overview of recent flow runs by time and duration of run. [Filters](#filters) control the detail of what's shown in the Run history.

![Highlighting the run history section of the dashboard.](/img/ui/orion-dash-history.png)

## Details

The details area of the dashboard provides a listing of flow runs that are scheduled or have attempted to execute. [Filters](#filters) control what's shown in the details section. 

Each listed flow run shows: 

- Flow name
- Flow run name
- Flow run state
- Actual or scheduled time of execution
- Tags
- Elapsed execution time (completed flow runs)
- Completed task runs (completed flow runs)

You can select any flow name or flow run name on the list to display further details. See the [Flows and Tasks](/ui/flows-and-tasks/) documentation for more information.

![Highlighting the details section of the dashboard.](/img/ui/orion-dash-details.png)