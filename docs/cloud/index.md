---
description: Observe and orchestrate your workflows with the hosted Prefect Cloud platform.
icon: material/cloud-outline
tags:
    - UI
    - dashboard
    - orchestration
    - Prefect Cloud
    - accounts
    - teams
    - workspaces
    - PaaS
title: Prefect Cloud
search:
  boost: 2
---

# Welcome to Prefect Cloud <span class="badge cloud"></span>

Prefect Cloud is a workflow coordination-as-a-service platform. Prefect Cloud provides all the capabilities of the [Prefect server](/host) and UI in a hosted environment, plus additional features such as automations, workspaces, and organizations.

!!! success "Getting Started with Prefect Cloud"
    Ready to jump right in and start running with Prefect Cloud? See the [Cloud Getting Started Guide](/cloud/cloud-quickstart/) to create a workspace, configure a local execution environment, and write your first Prefect Cloud-monitored flow run.

![Viewing a workspace dashboard in the Prefect Cloud UI.](/img/ui/cloud-workspace-dashboard.png)

Prefect Cloud includes all the features in the open-source Prefect server plus the following:

!!! cloud-ad "Prefect Cloud features"
    Features only available on Prefect Cloud include:

    - [User accounts](#user-accounts) &mdash; personal accounts for working in Prefect Cloud. 
    - [Workspaces](/cloud/workspaces/) &mdash; isolated environments to organize your flows, deployments, and flow runs.
    - [Automations](/cloud/automations/) &mdash; configure triggers, actions, and notifications in response to real-time monitoring events.
    - [Email notifications](/cloud/automations/) &mdash; send email alerts from Prefect's server based on automation triggers.
    - [Organizations](/cloud/organizations/) &mdash; user and workspace management features that enable collaboration for larger teams.
    - [Service accounts](/cloud/users/service-accounts/) &mdash; configure API access for running agents or executing flow runs on remote infrastructure.
    - [Custom role-based access controls (RBAC)](/cloud/users/roles/) &mdash; assign users granular permissions to perform certain activities within an organization or a workspace.
    - [Single Sign-on (SSO)](/cloud/users/sso/) &mdash; authentication using your identity provider.
    - [Audit Log](/cloud/users/audit-log/) &mdash; a record of user activities to monitor security and compliance.
    - Collaborators &mdash; invite others to work in your [workspace](/cloud/workspaces/#workspace-collaborators) or [organization](/cloud/organizations/#organization-members).

## User accounts

When you sign up for Prefect Cloud, a personal account is automatically provisioned for you. A personal account gives you access to profile settings where you can view and administer your: 

- Profile, including profile handle and image
- API keys

As a personal account owner, you can create a [workspace](#workspaces) and invite collaborators to your workspace. 

[Organizations](#organizations) in Prefect Cloud enable you to invite users to collaborate in your workspaces with the ability to set [role-based access controls (RBAC)](#roles-and-custom-permissions) for organization members. Organizations may also configure [service accounts](#service-accounts) with API keys for non-user access to the Prefect Cloud API.

!!! cloud-ad "Prefect Cloud plans for teams of every size"
    See the [Prefect Cloud plans](https://www.prefect.io/pricing/) for details on options for individual users and teams.

## Workspaces

A workspace is an isolated environment within Prefect Cloud for your flows, deployments, and block configuration. See the [Workspaces](/cloud/workspaces/) documentation for more information about configuring and using workspaces.

Each workspace keeps track of its own:

- [Flow runs](/concepts/flows/) and task runs executed in an environment that is [syncing with the workspace](/cloud/#workspaces)
- [Flows](/concepts/flows/) associated with flow runs and deployments observed by the Prefect Cloud API
- [Deployments](/concepts/deployments/)
- [Work pools](/concepts/work-pools/)
- [Blocks](/concepts/blocks/) and [storage](/concepts/storage/)
- [Automations](/cloud/automations/)

When you first log into Prefect Cloud and create your workspace, it will most likely be empty. Don't Panic &mdash; you just haven't run any flows tracked by this workspace yet. See the [Prefect Cloud Quickstart](/cloud/cloud-quickstart/) to configure a local execution environment and start tracking flow runs in Prefect Cloud. 

![Viewing a workspace dashboard in the Prefect Cloud UI.](/img/ui/cloud-new-workspace.png)

## Events

Prefect Cloud allows you to see your [events](https://docs.prefect.io/2.10.13/cloud/events/). 
![Prefect UI](/img/ui/event-feed.png)


## Automations

Prefect Cloud [automations](/cloud/automations/) provide additional notification capabilities as the open-source Prefect server. Automations enable you to configure triggers and actions that can kick off flow runs, pause deployments, or send custom notifications in response to real-time monitoring events. 

## Organizations <span class="badge orgs"></span>

A Prefect Cloud [organization](/cloud/organizations/) is a type of account available on Prefect Cloud that enables more extensive and granular control over workspace collaboration. Within an organization account you can:

- Invite members to join the organization.
- Create organization workspaces.
- Configure members roles and permissions within the organization and for individual workspaces.
- Create service accounts that have credentials for non-user API access.

See the [Organizations](/cloud/organizations/) documentation for more information about managing users, service accounts, and workspaces in a Prefect Cloud organization.

## Service accounts <span class="badge orgs"></span>

Service accounts enable you to create a Prefect Cloud API key that is not associated with a user account. Service accounts are typically used to configure API access for running agents or executing flow runs on remote infrastructure. 

See the [service accounts](/cloud/users/service-accounts/) documentation for more information about creating and managing service accounts in a Prefect Cloud organization.

## Roles and custom permissions <span class="badge orgs"></span>

Role-based access control (RBAC) functionality in Prefect Cloud enables you to assign users granular permissions to perform certain activities within an organization or a workspace.

See the [role-based access controls (RBAC)](../cloud/users/roles/) documentation for more information about managing user roles in a Prefect Cloud organization.

## Single Sign-on (SSO) <span class="badge orgs"></span> <span class="badge enterprise"></span>

Prefect Cloud's [Organization and Enterprise plans](https://www.prefect.io/pricing) offer [single sign-on (SSO)](/cloud/users/sso/) authentication integration with your team’s identity provider. SSO integration can bet set up with identity providers that support OIDC and SAML.

## Audit Log <span class="badge orgs"></span> <span class="badge enterprise"></span>

Prefect Cloud's [Organization and Enterprise plans](https://www.prefect.io/pricing) offer [Audit Log](/cloud/users/audit-log/) compliance and transparency tools. Audit logs provide a chronological record of activities performed by users in your organization, allowing you to monitor detailed actions for security and compliance purposes. 

## Prefect Cloud REST API

The [Prefect REST API](/api-ref/rest-api/) is used for communicating data from Prefect clients to Prefect Cloud or a local Prefect server so that orchestration can be performed. This API is mainly consumed by Prefect clients like the Prefect Python Client or the Prefect UI.

!!! note "Prefect Cloud REST API interactive documentation"
    Prefect Cloud REST API documentation is available at <a href="https://app.prefect.cloud/api/docs" target="_blank">https://app.prefect.cloud/api/docs</a>.


## Start using Prefect Cloud

To create an account or sign in with an existing Prefect Cloud account, go to [https://app.prefect.cloud/](https://app.prefect.cloud/).

Then follow the steps in our [Prefect Cloud Quickstart](/ui/cloud-quickstart/) to create a workspace, configure a local execution environment, and start running workflows with Prefect Cloud.

!!! tip "Need help?"
    Get your questions answered with a Prefect product advocate by [Booking A Rubber Duck](https://calendly.com/prefect-experts/prefect-product-advocates)!
