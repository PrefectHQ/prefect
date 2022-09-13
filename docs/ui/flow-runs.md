---
description: View and inspect your flow runs in the Prefect UI and Prefect Cloud.
tags:
    - Orion
    - UI
    - flow runs
    - observability
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
- [Flow run history](#flow-run-history)
- [Flow run details](#flow-run-details)

## Filters

The **Filters** area at the top of the page provides controls that enable you to display selected details of flow runs on the dashboard. Filters include date intervals, flow run state, flow name, deployment name, and tags. 

![Highlighting the filters section of the dashboard.](/img/ui/orion-dash-filters.png)

## Flow run history

The **run history** area of the page provides an overview of recent flow runs by time and duration of run. [Filters](#filters) control the detail of what's shown in the Run history.

![Highlighting the run history section of the dashboard.](/img/ui/orion-dash-history.png)

## Flow run details

The flow run details area of the page provides a listing of flow runs that are scheduled or have attempted to execute. 

You can select any flow name or flow run name on the list to display further details. See the [Flows and Tasks](/ui/flows-and-tasks/) documentation for more information.

![Highlighting the details section of the flow runs page.](/img/ui/orion-dash-details.png)

The default view shows all flow runs observed by the Prefect API and scheduled flow runs for deployments. You can use filters to display only the flow runs that meet your filter criteria, such as status or tags.

Each row in the flow run details shows information about a specific completed, in progress, or scheduled flow run.

![Information displayed for a flow run in the UI](/img/ui/orion-flow-run-examples.png)

For each flow run listed, you'll see:

- Flow name
- Flow run name
- Tags on the deployment, flow, or tasks within the flow
- [State](/concepts/states/) of the flow run
- Scheduled or actual start time for the flow run
- Elapsed run time for completed flow runs
- Number of completed task runs for the flow

You can see additional details about the flow by [selecting the flow name](#inspect-a-flow). You can see detail about the flow run by [selecting the flow run name](#inspect-a-flow-run).

## Inspect a flow

If you select the name of a flow in the dashboard, the UI displays details about the flow.

![Details for a flow in the Prefect UI](/img/ui/orion-flow-details.png)

If deployments have been created for the flow, you'll see them here. Select the deployment name to see further details about the deployment.

On this page you can also:

- Copy the ID of the flow or delete the flow from the API by using the command button to the right of the flow name. Note that this does not delete your flow code. It only removes any record of the flow from the Prefect API.
- Pause a schedule for a deployment by using the toggle control.
- Copy the ID of the deployment or delete the deployment by using the command button to the right of the deployment.

## Inspect a flow run

If you select the name of a flow run in the dashboard, the UI displays details about that specific flow run.

![Display details for a specific flow run.](/img/ui/orion-flow-run-details.png)

You can see details about the flow run including:

- Flow and flow run names
- State
- Elapsed run time
- Flow and flow run IDs
- Timestamp of flow run creation (time of flow run for ad-hoc flow runs, or time when the deployment was created or updated for scheduled deployments)
- Flow version
- Run count
- [Infrastructure](/concepts/infrastructure/) used by the flow run
- Tags
- Logs
- Task runs
- Subflow runs
- [Radar](#radar-view) view of the flow run

**Logs** displays all log messages for the flow run. See [Logging](/concepts/logs/) for more information about configuring and customizing log messages. Logs are the default view for a flow run.

**Task Runs** displays a listing of task runs executed within the flow run. Task runs are listed by flow name, flow run name, and task run name.

![Display all task runs.](/img/ui/orion-task-runs.png)

**Sub Flow Runs** displays any subflows for the flow run.

![Display any subflow runs for the parent flow run.](/img/ui/orion-subflows.png)

## Radar view

When viewing flow run details, the Radar shows a simple visualization of the task runs executed within the flow run. Click on the **Radar** area to see a detailed, hierarchical visualization of the task execution paths for the flow run.

Zoom out to see the entire flow hierarchy, and zoom in and drag the radar around to see details and connections between tasks. Select any task to focus the view on that task.

![Radar view of flow and task relationships.](/img/ui/orion-flow-radar.png)

## Troubleshooting flows

If you're having issues with a flow run, Prefect provides multiple tools to help you identify issues, re-run flows, and even delete a flow or flow run.

Flows may end up in states other than Completed. This is where Prefect really helps you out. If a flow ends up in a state such as Pending, Failed, or Cancelled, you can:

- Check the logs for the flow run for errors.
- Check the task runs to see where the error occurred.
- Check [work queues](/ui/work-queues/) to make sure there's a queue that can service the flow run based on tags, deployment, or flow runner.
- Make sure an [agent](/concepts/work-queues/) is running in your execution environment and is configured to pull work from an appropriate work queue.

If you need to delete a flow or flow run: 

In the Prefect UI or Prefect Cloud, go the page for flow or flow run and the select the **Delete** command from the button to the right of the flow or flow run name.

From the command line in your execution environment, you can delete a flow run by using the `prefect flow-run delete` CLI command, passing the ID of the flow run. 

<div class="terminal">
```bash
$ prefect flow-run delete 'a55a4804-9e3c-4042-8b59-b3b6b7618736'
```
</div>

To get the flow run ID, see [Inspect a flow run](#inspect-a-flow-run). 

## Flow run retention policy

!!! info "Prefect Cloud feature"
    The Flow Run Retention Policy setting is only applicable in Prefect Cloud.

Flow runs in Prefect Cloud are retained according to the Flow Run Retention Policy setting in your personal account or organization profile. The policy setting applies to all workspaces owned by the personal account or organization respectively. 

The flow run retention policy represents the number of days each flow run is available in the Prefect Cloud UI, and via the Prefect CLI and API after it ends. Once a flow run reaches a terminal state ([detailed in the chart here](/concepts/states/#state-types)), it will be retained until the end of the flow run retention period. 

!!! tip "Flow Run Retention Policy keys on terminal state"
    Note that, because Flow Run Retention Policy keys on terminal state, if two flows start at the same time, but reach a terminal state at different times, they will be removed at different times according to when they each reached their respective terminal states.

This retention policy applies to all [details about a flow run](/ui/flow-runs/#inspect-a-flow-run), including its task runs. Subflow runs follow the retention policy independently from their parent flow runs, and are removed based on the time each subflow run reaches a terminal state. 

If you or your organization have needs that require a tailored retention period, [contact our Sales team](https://www.prefect.io/pricing).