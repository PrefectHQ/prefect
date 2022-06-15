---
description: Learn how to access and configure the Prefect UI and Prefect Cloud.
tags:
    - Orion
    - UI
    - dashboard
    - Prefect Cloud
---

# Prefect UI & Prefect Cloud Overview

The Prefect UI provides an overview of all of your flows. It was designed around a simple question: what's the health of my system?

There are two ways to access the UI:

- The [Prefect UI](#using-the-orion-ui) gives you insight into the flows running with any local Prefect API server instance.
- [Prefect Cloud](/ui/cloud/) is a hosted service that provides all the capabilities of the Prefect API server and orchestration engine, plus personal accounts, workspaces, and collaborators.

The UI displays many useful insights about your flow runs, including:

- Flow run summaries
- Deployed flow details
- Scheduled flow runs
- Warnings for late or failed runs
- Task run details 
- Radar flow and task dependency visualizer 
- Logs

You can filter the information displayed in the UI by time, flow state, and tags.

## Using the Prefect UI

The Prefect UI is available in any environment where the Prefect API server is running with `prefect orion start`.

<div class="terminal">
```bash
$ prefect orion start
Starting...

 ___ ___ ___ ___ ___ ___ _____    ___  ___ ___ ___  _  _
| _ \ _ \ __| __| __/ __|_   _|  / _ \| _ \_ _/ _ \| \| |
|  _/   / _|| _|| _| (__  | |   | (_) |   /| | (_) | .` |
|_| |_|_\___|_| |___\___| |_|    \___/|_|_\___\___/|_|\_|

Configure Prefect to communicate with the server with:

    prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api

Check out the dashboard at http://127.0.0.1:4200
```
</div>

When the Prefect API server is running, you can access the UI at [http://127.0.0.1:4200](http://127.0.0.1:4200).

![Prefect UI dashboard.](/img/ui/orion-dashboard.png)

The following sections provide details about Prefect UI pages and visualizations:

- [Flow Runs](/ui/dashboard/) dashboard provides a high-level overview of your flows, tasks, and deployments.
- [Flow and flow run](/ui/flows-and-tasks/) pages let you dig into details of flow runs and task runs.
- [Filters](/ui/dashboard/#filters) enable you to customize the display based on flow state, tags, execution time, and more.
- [Flows](/ui/flows/) provides an overview of specific flows tracked by by the API.
- [Deployments](/ui/deployments/) provides an overview of flow deployments that you've created on the API.
- [Work Queues](/ui/work-queues/) enable you to create and manage work queues that distribute flow runs to agents.

## Navigating the UI

Use the left side of the Prefect UI to navigate between pages.

| Page | Description |
| --- | --- |
| **Flow Runs**   | Displays the **Flow Runs** dashboard displaying flow run status for the current API server or Prefect Cloud workspace. From this dashboard you can create filters](/ui/dashboard/#filters) to display only certain flow runs, or click into details about specific flows or flow runs. |
| **Flows**       | Displays a searchable list of flows tracked by the API. |
| **Deployment**  | Displays flow [deployments](/concepts/deployments/) created on the API. |
| <span class="no-wrap">**Work Queues**</span> | Displays configured [work queues](/ui/work-queues/) and enables creating new work queues. |

In Prefect Cloud, the Prefect icon returns you to the workspaces list. Currently, you can create only one workspace per personal account, but you may have access to other workspaces as a collaborator. See the [Prefect Cloud Workspaces](/ui/cloud/#workspaces) documentation for details. 

## Prefect Cloud

[Prefect Cloud](https://beta.prefect.io) provides a hosted server and UI instance for running and monitoring deployed flows. Prefect Cloud includes:

- All of the features of the local Prefect UI.
- A personal account and workspace.
- API keys to sync deployments and flow runs with the Prefect Cloud API.
- A hosted Prefect database that stores flow and task run history.

See the [Prefect Cloud](/ui/cloud/) documentation for details about setting up accounts, workspaces, and API keys.