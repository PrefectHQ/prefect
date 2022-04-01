---
description: Work with flows, deployments, and tasks in the Prefect UI and Prefect Cloud.
tags:
    - Orion
    - UI
    - flows
    - tasks
    - flow runs
    - deployments
    - logging
    - Prefect Cloud
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

You can see details about the flow run including:

- State
- Tags
- Start and end times and elapsed time
- Version
- Timeline of task and subflow runs
- Task runs
- Subflow runs
- Logs
- [Radar](#radar-view) view of the flow run

Click **Task Runs** to see the task run details for the flow run.

Click **Subflow Runs** to see any subflows for the flow run.

Click **Logs** to see log messages for the flow run. See [Logging](/concepts/logs/) for more information about configuring and customizing log messages.

![Display logs for a specific flow run.](/img/ui/orion-flow-run-logs.png)

## Task runs

On the dashboard, click **Task Runs** to see a listing of recent task runs. Task runs are listed by flow name, flow run name, and task run name.

You can use [Filters](/ui/filters/) to display only the task runs that meet your filter criteria.

![Display all task runs.](/img/ui/orion-task-runs.png)

## Radar view

When viewing flow run details, the Radar block shows a simple visualization of the task runs executed within the flow run. Click on the **Radar** block to see a detailed, hierarchical visualization of the task execution paths for the flow run.

![Radar view of flow and task relationships.](/img/ui/orion-flow-radar.png)