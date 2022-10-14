---
description: Workspaces are isolated environments for flows and deployments within Prefect Cloud.
tags:
    - UI
    - Prefect Cloud
    - workspaces
    - deployments
---

# Workspaces <span class="badge cloud"></span>

A workspace is an isolated environment within Prefect Cloud for your flows and deployments. Workspaces could be used in any way you like to organize or compartmentalize your workflows. For example, you could use separate workspaces to isolate dev, staging, and prod environments, or to provide separation between different teams.

Prefect Cloud allows one workspace per personal user account and three collaborators on a [Starter](https://www.prefect.io/pricing/) plan. See [Pricing](https://www.prefect.io/pricing/) if you need additional workspaces or users.  

Each workspace keeps track of its own:

- [Flow runs](/ui/flow-runs/) and task runs executed in an environment that is [syncing with the workspace](/ui/cloud/#workspaces)
- [Flows](/concepts/flows/) associated with flow runs or deployments observed by the Prefect Cloud API
- [Deployments](/concepts/deployments/)
- [Work queues](/concepts/work-queues/)
- [Blocks](/ui/blocks/) and [Storage](/concepts/storage/)
- [Notifications](/ui/notifications/)

When you first log into Prefect Cloud, you will be prompted to create your own initial workspace.

![Viewing a workspace dashboard in the Prefect Cloud UI.](/img/ui/cloud-new-workspace.png)