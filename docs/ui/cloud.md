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

# Welcome to Prefect Cloud <span class="badge cloud"></span>

Prefect Cloud is a workflow coordination-as-a-service platform. Prefect Cloud provides all the capabilities of the [Prefect Orion Server](https://docs.prefect.io/tutorials/orion/?h=server#running-the-prefect-server) and [UI](/ui/overview/) in a hosted environment, including:

- [Flow runs](/ui/flow-runs/) dashboard, including:
    - Details of completed and upcoming scheduled flow runs.
    - Warnings for late or failed runs.
    - Logs for individual flow and task runs.
- [Flows](/ui/flows/) observed by the Prefect Cloud API. 
- [Deployments](/ui/deployments/) created on the Prefect Cloud API. You can also use the Prefect Cloud UI to create ad-hoc flow runs from deployments.
- [Work queues](/ui/work-queues/) created to queue work for agents.
- [Blocks](/ui/blocks/) configured for storage or infrastructure used by your flow runs.
- [Notifications](/ui/notifications/) configured to alert on flow run state changes.

!!! info "Prefect Cloud features"
    Features only available on Prefect Cloud include:

    - [User accounts](#user-accounts) &mdash; personal accounts for working in Prefect Cloud. 
    - [Workspaces](/ui/workspaces/) &mdash; isolated environments to organize your flows, deployments, and flow runs.
    - [Organizations](/ui/organizations/) &mdash; user and workspace management features that enable collaboration for larger teams.
    - [Service accounts](/ui/service-accounts/) &mdash; configure API access for running agents or executing flow runs on remote infrastructure.
    - [Custom role-based access controls (RBAC)](/ui/roles/) &mdash; assign users granular permissions to perform certain activities within an organization or a workspace.
    - [Single Sign-on (SSO)](/ui/sso/) authentication using your identity provider.
    - [Audit Log](/ui/audit-log/) record of user activities to monitor security and compliance.
    - Collaborators &mdash; invite others to work in your workspace or organization.
    - [Email notifications](/ui/notifications/) &mdash; configure email alerts based on flow run states and tags.

![Viewing a workspace dashboard in the Prefect Cloud UI.](/img/ui/cloud-workspace-dashboard.png)

## User accounts

When you sign up for Prefect Cloud, a personal account is automatically provisioned for you. A personal account gives you access to profile settings where you can view and administer your: 

- Profile, including profile handle and image
- API keys

As a personal account owner, you can create a [workspace](#workspaces) and invite collaborators to your workspace. 

[Organizations](#organizations) in Prefect Cloud enable you to invite users to collaborate in your workspaces with the ability to set [role-based access controls (RBAC)](#roles-and-custom-permissions) for organization members. Organizations may also configure [service accounts](#service-accounts) with API keys for non-user access to the Prefect Cloud API.

!!! tip "Prefect Cloud plans for teams of every size"
    See the [Prefect Cloud plans](https://www.prefect.io/pricing/) for details on options for individual users and teams.

## Workspaces

A workspace is an isolated environment within Prefect Cloud for your flows, deployments, and block configuration. See the [Workspaces](/ui/workspaces/) documentation for more information about configuring and using workspaces.

Each workspace keeps track of its own:

- [Flow runs](/ui/flow-runs/) and task runs executed in an environment that is [syncing with the workspace](/ui/cloud/#workspaces)
- [Flows](/concepts/flows/) associated with flow runs and deployments observed by the Prefect Cloud API
- [Deployments](/concepts/deployments/)
- [Work queues](/concepts/work-queues/)
- [Blocks](/ui/blocks/) and [storage](/concepts/storage/)
- [Notifications](/ui/notifications/)

When you first log into Prefect Cloud and create your workspace, it will most likely be empty. Don't Panic &mdash; you just haven't run any flows tracked by this workspace yet. The next steps will show you how to [get started with Prefect Cloud](/ui/cloud-getting-started/). 

![Viewing a workspace dashboard in the Prefect Cloud UI.](/img/ui/cloud-new-workspace.png)

## Organizations <span class="badge orgs"></span>

An organization is a type of account available on Prefect Cloud that enables more extensive and granular control over workspace collaboration. 

Within an organization account you can:

- Invite members to join the organization.
- Create organization workspaces.
- Configure members roles and permissions within the organization and for individual workspaces.
- Create service accounts that have credentials for non-user API access.

See the [Organizations](/ui/organizations/) documentation for more information about managing users, service accounts, and workspaces in a Prefect Cloud organization.

## Service accounts <span class="badge orgs"></span>

Service accounts enable you to create a Prefect Cloud API key that is not associated with a user account. Service accounts are typically used to configure API access for running agents or executing flow runs on remote infrastructure. 

See the [service accounts](/ui/service-accounts/) documentation for more information about creating and managing service accounts in a Prefect Cloud organization.

## Roles and custom permissions <span class="badge orgs"></span>

Role-based access control (RBAC) functionality in Prefect Cloud enables you to assign users granular permissions to perform certain activities within an organization or a workspace.

See the [role-based access controls (RBAC)](/ui/roles/) documentation for more information about managing user roles in a Prefect Cloud organization.

## Single Sign-on (SSO) <span class="badge orgs"></span> <span class="badge enterprise"></span>

Prefect Cloud's [Organization and Enterprise plans](https://www.prefect.io/pricing) offer [single sign-on (SSO)](/ui/sso/) authentication integration with your team’s identity provider. SSO integration can bet set up with identity providers that support OIDC and SAML.

## Audit Log <span class="badge orgs"></span> <span class="badge enterprise"></span>

Prefect Cloud's [Organization and Enterprise plans](https://www.prefect.io/pricing) offer [Audit Log](/ui/audit-log/) compliance and transparency tools. Audit logs provide a chronological record of activities performed by users in your organization, allowing you to monitor detailed actions for security and compliance purposes. 

## Start using Prefect Cloud

To create an account or sign in with an existing Prefect Cloud account, go to [http://app.prefect.cloud/](http://app.prefect.cloud/).

Then see [Getting Started with Prefect Cloud](/ui/cloud-getting-started/) to set up your profile and workspace, configure your workflow execution environment, and start running workflows with Prefect Cloud.