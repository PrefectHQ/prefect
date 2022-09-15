---
description: Prefect Cloud provides a hosted coordination-as-a-service platform for your workflows.
tags:
    - UI
    - dashboard
    - Prefect Cloud
    - accounts
    - teams
    - workspaces
    - SaaS
---

# Welcome to Prefect Cloud

Prefect Cloud is a workflow coordination-as-a-service platform. Prefect Cloud provides all the capabilities of the [Prefect UI](/ui/overview/) in a hosted environment, including:

- [Flow run](/ui/flow-runs/) summaries
- Details of upcoming scheduled flow runs
- Warnings for late or failed runs
- [Flows](/ui/flows/) observed by the Prefect Cloud API
- Task runs within flow run, including the Radar task dependency visualizer 
- Logs
- [Deployments](/ui/deployments/)
- [Work queues](/ui/work-queues/)
- [Blocks](/ui/blocks/)
- [Notifications](/ui/notifications/)

You can also use the Prefect Cloud UI to create ad-hoc flow runs from deployments.

Features only available on Prefect Cloud include:

- User accounts: personal accounts for working in Prefect Cloud. 
- Workspaces: isolated environments for your flows, deployments, and flow runs.
- Collaborators: invite others to work in your workspace.
- Email notifications: configure email alerts based on flow run states and tags.

![Viewing a workspace dashboard in the Prefect Cloud UI.](/img/ui/cloud-workspace-dashboard.png)

## User accounts

When you sign up for Prefect Cloud, a personal account is automatically provisioned for you. A personal account gives you access to profile settings where you can view and administer your: 

- Profile, including profile handle and image
- API keys

As a personal account owner, you can create a [workspace](#workspaces) and invite collaborators to your workspace. 

!!! tip "Prefect Cloud plans for teams of every size"
    See the [Prefect Cloud plans](https://www.prefect.io/pricing/) for details on options for individual users and teams.

## Workspaces

A workspace is an isolated environment within Prefect Cloud for your flows and deployments. Workspaces could be used in any way you like to organize or compartmentalize your workflows. For example, you could use separate workspaces to isolate dev, staging, and prod environments, or to provide separation between different teams.

Prefect Cloud allows one workspace per personal user account and three collaborators on a [Starter](https://www.prefect.io/pricing/) plan. See [Pricing](https://www.prefect.io/pricing/) if you need additional workspaces or users.  

Each workspace keeps track of its own:

- [Flow runs](/ui/flow-runs/) and task runs executed in an environment that is [syncing with the workspace](/ui/cloud/#workspaces)
- [Flows](/concepts/flows/) associated with flow runs or deployments observed by the Prefect Cloud API
- [Deployments](/concepts/deployments/)
- [Work queues](/concepts/work-queues/)
- [Blocks](/ui/blocks/) and [Storage](/concepts/storage/)
- [Notifications](/ui/notifications/)

When you first log into Prefect Cloud and create your workspace, it will most likely be empty. Don't Panic &mdash; you just haven't run any flows tracked by this workspace yet. The next steps will show you how to [get started with Prefect Cloud](/ui/cloud-getting-started/). 

![Viewing a workspace dashboard in the Prefect Cloud UI.](/img/ui/cloud-new-workspace.png)

## Start using Prefect Cloud

To create an account or sign in with an existing Prefect Cloud account, go to [http://app.prefect.cloud/](http://app.prefect.cloud/).

Then see [Getting Started with Prefect Cloud](/ui/cloud-getting-started/) to set up your profile and workspace, configure your workflow execution environment, and start running workflows with Prefect Cloud.