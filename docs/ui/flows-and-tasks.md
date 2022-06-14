---
description: Work with flows and flow runs in the Prefect UI and Prefect Cloud.
tags:
    - Orion
    - UI
    - flows
    - tasks
    - flow runs
    - logging
    - Prefect Cloud
---

# Flows and Tasks

The bottom area of the Prefect UI dashboard displays details about your flow and task runs.

![Prefect UI dashboard.](/img/ui/orion-dash-details.png)

The default view shows all flow runs observed by the Prefect API and scheduled flow runs for deployments. You can use filters to display only the flow runs that meet your filter criteria, such as status or tags.

## Flow run details

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
- [Flow runner](/concepts/flow-runners/) used by the flow run
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

When viewing flow run details, the Radar shows a simple visualization of the task runs executed within the flow run. Click on the **Radar** block to see a detailed, hierarchical visualization of the task execution paths for the flow run.

Zoom zoom out to see the entire flow hierarchy, and zoom in and drag the radar around to see details and connections between tasks. Select any task to focus the view on that task.

![Radar view of flow and task relationships.](/img/ui/orion-flow-radar.png)

## Troubleshooting flows

If you're having issues with a flow run, Prefect provides multiple tools to help you identify issues, re-run flows, and even delete a flow or flow run.

Flows may end up in states other than Completed. This is where Prefect really helps you out. If a flow ends up in a state such as Pending, Failed, or Cancelled, you can:

- Check the logs for the flow run for errors.
- Check the task runs to see where the error occurred.
- Check [work queues](/ui/work-queues/) to make sure there's a queue that can service the flow run based on tags, deployment, or flow runner.
- Make sure an [agent](/concepts/work-queues/) is running in your execution environment and is configured to pull work from an appropriate work queue.

If you need to delete a flow or flow run: 

In the Prefect UI or Prefect Cloud, go the the page for flow or flow run and the select the **Delete** command from the button to the right of the flow or flow run name.

From the command line in your execution environment, you can delete a flow run by using the `prefect flow-run delete` CLI command, passing the ID of the flow run. 

<div class="terminal">
```bash
$ prefect flow-run delete 'a55a4804-9e3c-4042-8b59-b3b6b7618736'
```
</div>

To get the flow run ID, see [Inspect a flow run](#inspect-a-flow-run). 