---
description: Working with flows, deployments, and tasks in the Orion UI.
tags:
    - Orion
    - UI
    - flows
    - tasks
    - flow runs
    - deployments
    - logging
    - Cloud
---

# Flows and Tasks

The bottom area of the Prefect Orion dashboard displays details about your flow and task runs.

![Prefect Orion UI dashboard.](/img/ui/orion-dash-details.png)

The default view shows all flows observed by the Orion API server. You can also see:

- Deployments
- [Flow runs](#flow-runs)
- [Task runs](#task-runs)

## Flow runs

On the dashboard, click **Flow Runs** to see a listing of recent runs. Flow runs are listed by flow name and flow run name.

You can use [Filters](/ui/filters/) to display only the flow runs that meet your filter criteria.

![Flow runs page list recent flow runs.](/img/ui/orion-flow-runs.png)

Click on a flow run name to display details for a specific flow run. 

![Display details for a specific flow run.](/img/ui/orion-flow-run-details.png)

Click **Logs** to see log messages for the flow run. See [Logging](/concepts/logs/) for more information about configuring and customizing log messages.

![Display logs for a specific flow run.](/img/ui/orion-flow-run-logs.png)

## Task runs

On the dashboard, click **Task Runs** to see a listing of recent task runs. Task runs are listed by flow name, flow run name, and task run name.

You can use [Filters](/ui/filters/) to display only the task runs that meet your filter criteria.

![Display all task runs.](/img/ui/orion-task-runs.png)

## Radar view

![Radar view of flow and task relationships.](/img/ui/orion-flow-radar.png)