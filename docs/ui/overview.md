---
description: Gain overall visibility and coordination of your workflows with Prefect UI and Prefect Cloud.
tags:
    - Orion
    - UI
    - dashboard
    - visibility
    - coordination
    - coordination plane
    - orchestration
    - Prefect Cloud
---

# Prefect UI & Prefect Cloud Overview

The Prefect UI provides an overview of all of your flows. It was designed around a simple question: what's the health of my system?

![Prefect UI](/img/ui/orion-dashboard.png)

There are two ways to access the UI:

- [Prefect Cloud](/ui/cloud/) is a hosted service that gives you observability over your flows, flow runs, and deployments, plus the ability to configure personal accounts, workspaces, and collaborators.
- The [Prefect Orion UI](#using-the-prefect-ui) is also available as an open source, locally hosted orchestration engine, API server, and UI, giving you insight into the flows running with any local Prefect Orion instance.

The Prefect UI displays many useful insights about your flow runs, including:

- Flow run summaries
- Deployed flow details
- Scheduled flow runs
- Warnings for late or failed runs
- Task run details 
- Radar flow and task dependency visualizer 
- Logs

You can filter the information displayed in the UI by time, flow state, and tags.

## Using the Prefect UI

The Prefect UI is available via [Prefect Cloud](/ui/cloud/) by logging into your account at [https://app.prefect.cloud/](https://app.prefect.cloud/).

The Prefect UI is also available in any environment where a Prefect Orion server is running with `prefect orion start`.

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

When the Prefect Orion server is running, you can access the Prefect UI at [http://127.0.0.1:4200](http://127.0.0.1:4200).

![Prefect UI](/img/ui/orion-dashboard.png)

The following sections provide details about Prefect UI pages and visualizations:

- [Flow Runs](/ui/flow-runs/) page provides a high-level overview of your flow runs.
- [Flows](/ui/flows/) provides an overview of specific flows tracked by by the API.
- [Deployments](/ui/deployments/) provides an overview of flow deployments that you've created on the API.
- [Work Queues](/ui/work-queues/) enable you to create and manage work queues that distribute flow runs to agents.
- [Blocks](/ui/blocks/) enable you to create and manage configuration for [blocks](/concepts/blocks/) such as [storage](/concepts/storage/).
- [Notifications](/ui/notifications/) enable you to create and manage alerts based on flow run states and tags.

## Navigating the UI

Use the left side of the Prefect UI to navigate between pages.

| Page | Description |
| --- | --- |
| **Flow Runs**      | Displays the **Flow Runs** dashboard displaying flow run status for the current API server or Prefect Cloud workspace. From this dashboard you can create [filters](/ui/flow-runs/#filters) to display only certain flow runs, or click into details about specific flows or flow runs. |
| **Flows**          | Displays a searchable list of flows tracked by the API. |
| **Deployments**    | Displays flow [deployments](/concepts/deployments/) created on the API. |
| <span class="no-wrap">**Work Queues**</span> | Displays configured [work queues](/ui/work-queues/) and enables creating new work queues. |
| **Blocks**         | Displays a list of [blocks](/ui/blocks/) configured on the API and enables configuring new blocks. |
| **Notifications**  | Displays a list of configured flow run state [notifications](/ui/notifications/) and enables configuring new notifications. |


In Prefect Cloud, the Prefect icon returns you to the workspaces list. Currently, you can create only one workspace per personal account, but you may have access to other workspaces as a collaborator. See the [Prefect Cloud Workspaces](/ui/cloud/#workspaces) documentation for details. 

## Prefect Cloud

[Prefect Cloud](https://app.prefect.cloud) provides a hosted server and UI instance for running and monitoring deployed flows. Prefect Cloud includes:

- All of the features of the local Prefect UI.
- A personal account and workspace.
- API keys to sync deployments and flow runs with the Prefect Cloud API.
- A hosted Prefect database that stores flow and task run history.

See the [Prefect Cloud](/ui/cloud/) documentation for details about setting up accounts, workspaces, and API keys.
