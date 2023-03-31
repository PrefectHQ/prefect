---
description: Gain overall visibility and coordination of your workflows with Prefect UI and Prefect Cloud.
icon: material/cloud-outline
tags:
    - UI
    - dashboard
    - visibility
    - coordination
    - coordination plane
    - orchestration
    - Prefect Cloud
---

# Prefect UI & Prefect Cloud 

The Prefect UI provides an overview of all of your flows. It was designed around a simple question: what's the health of my system?

![Prefect UI](../img/ui/prefect-dashboard.png)

There are two ways to access the UI:

- [Prefect Cloud](/ui/cloud/) is a hosted service that gives you observability over your flows, flow runs, and deployments, plus the ability to configure personal accounts, workspaces, and collaborators.
- The [Prefect UI](#using-the-prefect-ui) is also available as an open source, locally hosted orchestration engine, API server, and UI, giving you insight into the flows running with any local Prefect server instance.

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

The Prefect UI is also available in any environment where a Prefect server is running with `prefect server start`.

<div class="terminal">
```bash
$ prefect server start
Starting...

 ___ ___ ___ ___ ___ ___ _____ 
| _ \ _ \ __| __| __/ __|_   _|
|  _/   / _|| _|| _| (__  | |
|_| |_|_\___|_| |___\___| |_|

Configure Prefect to communicate with the server with:

    prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api

Check out the dashboard at http://127.0.0.1:4200
```
</div>

When the Prefect server is running, you can access the Prefect UI at [http://127.0.0.1:4200](http://127.0.0.1:4200).

![Prefect UI](../img/ui/prefect-dashboard.png)

The following sections provide details about Prefect UI pages and visualizations:

- [Flow Runs](/ui/flow-runs/) page provides a high-level overview of your flow runs.
- [Flows](/ui/flows/) provides an overview of specific flows tracked by by the API.
- [Deployments](/ui/deployments/) provides an overview of flow deployments that you've created on the API.
- [Work Pools](/ui/work-pools/) enable you to create and manage work pools that distribute flow runs to agents.
- [Blocks](/ui/blocks/) enable you to create and manage configuration for [blocks](/concepts/blocks/) such as [storage](/concepts/storage/).
- [Notifications](/ui/notifications/) enable you to create and manage alerts based on flow run states and tags.
- [Task Run Concurrency Limits](/ui/task-concurrency/) enable you to restrict the number of certain tasks that can run simultaneously.

## Navigating the UI

Use the left side of the Prefect UI to navigate between pages.

| Page | Description |
| --- | --- |
| **Flow Runs**      | Displays the **Flow Runs** dashboard displaying flow run status for the current API server or Prefect Cloud workspace. From this dashboard you can create [filters](/ui/flow-runs/#filters) to display only certain flow runs, or click into details about specific flows or flow runs. |
| **Flows**          | Displays a searchable list of flows tracked by the API. |
| **Deployments**    | Displays flow [deployments](/concepts/deployments/) created on the API. |
| **Work Pools** | Displays configured [work pools](/ui/work-pools/) and enables creating new work pools. |
| **Blocks**         | Displays a list of [blocks](/ui/blocks/) configured on the API and enables configuring new blocks. |
| **Notifications**  | Displays a list of configured [notifications](/ui/notifications/) and enables configuring new notifications. |
| <span class="no-wrap">**Task Run Concurrency**</span> | Displays a list of configured [task run concurrency limits](/ui/task-concurrency/) and enables configuring new limits. |

In Prefect Cloud, the Prefect icon returns you to the workspaces list. Currently, you can create only one workspace per personal account, but you may have access to other workspaces as a collaborator. See the [Prefect Cloud Workspaces](/ui/cloud/#workspaces) documentation for details. 

## Prefect Cloud

[Prefect Cloud](https://app.prefect.cloud) provides a hosted server and UI instance for running and monitoring deployed flows. Prefect Cloud includes:

- All of the features of the local Prefect UI.
- A personal account and workspace.
- API keys to sync deployments and flow runs with the Prefect Cloud API.
- A hosted Prefect database that stores flow and task run history.

See the [Prefect Cloud](/ui/cloud/) documentation for details about setting up accounts, workspaces, and API keys.

## Prefect REST API

The [Prefect REST API](/api-ref/rest-api/) is used for communicating data from Prefect clients to Prefect Cloud or a local Prefect server so that orchestration can be performed. This API is mainly consumed by clients like the Prefect Python Client or the Prefect UI.

!!! note "Prefect REST API interactive documentation"
    Prefect Cloud REST API documentation is available at <a href="https://app.prefect.cloud/api/docs" target="_blank">https://app.prefect.cloud/api/docs</a>.

    The Prefect REST API documentation for a local instance run with with `prefect server start` is available at <a href="http://localhost:4200/docs" target="_blank">http://localhost:4200/docs</a> or the `/docs` endpoint of the [`PREFECT_API_URL`](/concepts/settings/#prefect_api_url) you have configured to access the server.

    The Prefect REST API documentation for locally run open-source Prefect servers is also available in the [Prefect REST API Reference](/api-ref/rest-api-reference/).
