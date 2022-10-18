---
description: Workspaces are isolated environments for flows and deployments within Prefect Cloud.
tags:
    - UI
    - Prefect Cloud
    - workspaces
    - deployments
---

# Workspaces <span class="badge cloud"></span>

A workspace is an isolated environment within Prefect Cloud for your flows and deployments. Workspaces are only available to Prefect Cloud accounts.

Workspaces could be used in any way you like to organize or compartmentalize your workflows. For example, you could use separate workspaces to isolate dev, staging, and prod environments, or to provide separation between different teams.

The number of available workspaces varies by [Prefect Cloud plan](https://www.prefect.io/pricing/). See [Pricing](https://www.prefect.io/pricing/) if you need additional workspaces or users.  

### Workspaces overview

When you first log into Prefect Cloud, you will be prompted to create your own initial workspace.

![Viewing a workspace dashboard in the Prefect Cloud UI.](/img/ui/cloud-new-workspace.png)

Select the **Prefect Logo** in the left navigation area to see all of the workspaces you can access. 

![Viewing all available workspaces in the Prefect Cloud UI.](/img/ui/all-workspaces.png)

Your list of available workspaces may include:

- Your own personal workspaces.
- Workspaces owned by other users, who have invited you to their workspace as a collaborator.
- Workspaces in an [organization](/ui/organizations/) to which you've been invited and have been given access to organization workspaces.

!!! info "Workspace-specific features"
    Each workspace keeps track of its own:

    - [Flow runs](/ui/flow-runs/) and task runs executed in an environment that is [syncing with the workspace](/ui/cloud/#workspaces)
    - [Flows](/concepts/flows/) associated with flow runs or deployments observed by the Prefect Cloud API
    - [Deployments](/concepts/deployments/)
    - [Work queues](/concepts/work-queues/)
    - [Blocks](/ui/blocks/) and [Storage](/concepts/storage/)
    - [Notifications](/ui/notifications/)

Your user permissions within workspaces may vary. [Organizations](/ui/organizations/) can assign roles and permissions at the workspace level.

