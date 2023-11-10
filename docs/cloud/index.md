---
description: Observe and orchestrate your workflows with the hosted Prefect Cloud platform.
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

Prefect Cloud is a workflow orchestration platform that provides all the capabilities of Prefect server plus additional features, such as:

- automations, events, and webhooks so you can create for event-driven workflows
- workspaces, RBAC, SSO, audit logs and related user management tools for collaboration
- push work pools for running flows on serverless infrastructure without a worker
- error summaries powered by Marvin AI to help you resolve errors faster

!!! success "Getting Started with Prefect Cloud"
    Ready to jump right in and start running with Prefect Cloud? See the [Quickstart](/getting-started/quickstart/) and follow the instructions on the **Cloud** tabs to write and deploy your first Prefect Cloud-monitored flow run.

![Viewing a workspace dashboard in the Prefect Cloud UI](/img/ui/cloud-dashboard.png)

Prefect Cloud includes all the features in the open-source Prefect server plus the following:

!!! cloud-ad "Prefect Cloud features"
    - [User accounts](#user-accounts) &mdash; personal accounts for working in Prefect Cloud.
    - [Workspaces](/cloud/workspaces/) &mdash; isolated environments to organize your flows, deployments, and flow runs.
    - [Automations](/cloud/automations/) &mdash; configure triggers, actions, and notifications in response to real-time monitoring events.
    - [Email notifications](/cloud/automations/) &mdash; send email alerts from Prefect's server based on automation triggers.
    - [Service accounts](/cloud/users/service-accounts/) &mdash; configure API access for running workers or executing flow runs on remote infrastructure.
    - [Custom role-based access controls (RBAC)](/cloud/users/roles/) &mdash; assign users granular permissions to perform certain activities within an account or a workspace.
    - [Single Sign-on (SSO)](/cloud/users/sso/) &mdash; authentication using your identity provider.
    - [Audit Log](/cloud/users/audit-log/) &mdash; a record of user activities to monitor security and compliance.
    - Collaborators &mdash; invite others to work in your [workspace](/cloud/workspaces/#workspace-collaborators) or [account](/cloud/) TK.
    - Error summaries  &mdash; (enabled by Marvin AI) distill the error logs of `Failed` and `Crashed` flow runs into actionable information.
    - [Push work pool](/guides/deployment/push-work-pools/) &mdash; run flows on your serverless infrastructure without running a worker.

## User accounts

When you sign up for Prefect Cloud, an account is automatically provisioned for you.
An account gives you access to profile settings where you can view and administer your:

- Profile, including profile handle and image
- API keys
- Preferences, including timezone and color mode
- Feature previews, if available

As an account owner, you can create a [workspace](#workspaces) and invite collaborators to your workspace.

Upgrading from a Prefect Cloud Free tier plan to a Pro tier or Enterprise tier plan enables additional functionality for adding workspaces and managing teams.
As an administrator you then have the ability to set [role-based access controls (RBAC)](#roles-and-custom-permissions) and configure [service accounts](#service-accounts).

!!! cloud-ad "Prefect Cloud plans for teams of every size"
    See the [Prefect Cloud plans](https://www.prefect.io/pricing/) for details enhancements for Pro and Enterprise tiers.

## Workspaces

A workspace is an isolated environment within Prefect Cloud for your flows, deployments, and block configuration.
See the [Workspaces](/cloud/workspaces/) documentation for more information about configuring and using workspaces.

Each workspace keeps track of its own:

- [Flow runs](/concepts/flows/) and task runs executed in an environment that is [syncing with the workspace](/cloud/#workspaces)
- [Flows](/concepts/flows/) associated with flow runs and deployments observed by the Prefect Cloud API
- [Deployments](/concepts/deployments/)
- [Work pools](/concepts/work-pools/)
- [Blocks](/concepts/blocks/) and [storage](/concepts/storage/)
- [Automations](/cloud/automations/)

![Viewing a workspace dashboard in the Prefect Cloud UI.](/img/ui/cloud-new-workspace.png)

## Events

Prefect Cloud allows you to see your [events](/cloud/events/).
![Prefect UI](/img/ui/event-feed.png)

## Automations

Prefect Cloud [automations](/cloud/automations/) provide additional notification capabilities beyond those in the open-source Prefect server.
Automations enable you to configure triggers and actions that can kick off flow runs, pause deployments, or send custom notifications in response to real-time monitoring events.

## Error summaries

Prefect Cloud error summaries, enabled by Marvin AI, distill the error logs of `Failed` and `Crashed` flow runs into actionable information.
To enable this feature and others powered by Marvin AI, visit the **Settings** page for your account.

## Service accounts <span class="badge pro"></span> <span class="badge enterprise"></span>

Service accounts enable you to create a Prefect Cloud API key that is not associated with a user account.
Service accounts are typically used to configure API access for running workers or executing flow runs on remote infrastructure.

See the [service accounts](/cloud/users/service-accounts/) documentation for more information about creating and managing service accounts.

## Roles and custom permissions <span class="badge pro"> </span><span class="badge enterprise"></span>

Role-based access control (RBAC) functionality in Prefect Cloud enables you to assign users granular permissions to perform certain activities within an account or a workspace.

See the [role-based access controls (RBAC)](../cloud/users/roles/) documentation for more information about managing user roles in a Prefect Cloud account.

## Single Sign-on (SSO) <span class="badge pro"></span> <span class="badge enterprise"></span>

Prefect Cloud's [Pro and Enterprise plans](https://www.prefect.io/pricing) offer [single sign-on (SSO)](/cloud/users/sso/) authentication integration with your team’s identity provider. SSO integration can bet set up with identity providers that support OIDC and SAML.
SCIM provisioning is also available with Enterprise plans.

## Audit log <span class="badge pro"></span> <span class="badge enterprise"></span>

Prefect Cloud's [Pro and Enterprise plans](https://www.prefect.io/pricing) offer [Audit Log](/cloud/users/audit-log/) compliance and transparency tools.
Audit logs provide a chronological record of activities performed by users in your account, allowing you to monitor detailed actions for security and compliance purposes.

## Prefect Cloud REST API

The [Prefect REST API](/api-ref/rest-api/) is used for communicating data from Prefect clients to Prefect Cloud or a local Prefect server so that orchestration can be performed.
This API is mainly consumed by Prefect clients like the Prefect Python Client or the Prefect UI.

!!! note "Prefect Cloud REST API interactive documentation"
    Prefect Cloud REST API documentation is available at <a href="https://app.prefect.cloud/api/docs" target="_blank">https://app.prefect.cloud/api/docs</a>.

## Start using Prefect Cloud

To create an account or sign in with an existing Prefect Cloud account, go to [https://app.prefect.cloud/](https://app.prefect.cloud/).

Then follow the steps in the UI to deploy your first Prefect Cloud-monitored flow run. For more details, see the [Prefect Quickstart](/getting-started/quickstart/) and follow the instructions on the **Cloud** tabs.

!!! tip "Need help?"
    Get your questions answered by a Prefect Product Advocate!
    [Book a Meeting](https://calendly.com/prefect-experts/prefect-product-advocates?utm_campaign=prefect_docs_cloud&utm_content=prefect_docs&utm_medium=docs&utm_source=docs)
