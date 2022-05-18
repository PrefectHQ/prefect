---
description: Learn about using Prefect Cloud.
tags:
    - UI
    - dashboard
    - Prefect Cloud
    - accounts
    - teams
    - workspaces
---

# Welcome to Prefect Cloud

Prefect Cloud is an orchestration-as-a-service platform. Prefect Cloud provides all the capabilities of the [Prefect UI](/ui/overview/) in a hosted environment, including:

- Flow run summaries
- Deployed flow details
- Scheduled flow runs
- Warnings for late or failed runs
- Task run details 
- Radar flow and task dependency visualizer 
- Logs

Features only available on Prefect Cloud include:

- User accounts: personal accounts for working in Prefect Cloud. 
- Workspaces: isolated environments for your flows and deployments.

## User accounts

As a new user, a personal account is automatically provisioned for you.

A personal account gives you access to profile settings where you can view and administer your: 

- Profile, including profile handle and image
- API keys

As a personal account owner, you can create workspaces.

While in the current beta phase, Prefect Cloud currently allows only one workspace per personal user account. In future, Prefect Cloud will enable users to create multiple workspaces and optionally invite collaborators to workspaces.

## Workspaces

A workspace is an isolated environment within Prefect Cloud for your flows and deployments. Workspaces could be used in any way you like to organize or compartmentalize your workflows. For example, you could use separate workspaces to isolate dev, staging, and prod environments, or to provide separation between different teams.

While in the current beta phase, Prefect Cloud currently allows only one workspace per user account. 

Each workspace keeps track of its own:

- Flow runs executed in an environment logged into the workspace
- Deployments
- Work queues

![Viewing a workspace dashboard in the Prefect Cloud UI.](/img/ui/cloud-workspace-dashboard.png)

## Start using Prefect Cloud

To create an account or sign in with an existing Prefect Cloud account, go to [http://beta.prefect.io/](http://beta.prefect.io/).

Then see [Getting Started with Prefect Cloud](/ui/cloud-getting-started/) to set up your profile and workspace, configure your workflow execution environment, and start running workflows with Prefect Cloud.