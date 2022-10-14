---
description: Workspaces are isolated environments for flows and deployments within Prefect Cloud.
tags:
    - UI
    - Prefect Cloud
    - workspaces
    - deployments
---

# Service Accounts <span class="badge cloud"></span> <span class="badge orgs"></span>

Service accounts enable you to create a Prefect Cloud API key that is not associated with a user account. Service accounts are typically used to configure API access for running agents or executing flow runs on remote infrastructure.

Select **Service Accounts** to view, create, or edit service accounts for your organization.

![Viewing service accoutns for an organization in Prefect Cloud.](/img/ui/service-accounts.png)

Service accounts are created at the organization level, but may be shared to individual workspaces within the organization. See [workspace sharing](#workspace-sharing) for more information.

!!! tip "Service account credentials"
    When you create a service account, Prefect Cloud creates a new API key for the account and provides the API configuration command for the execution environment. Save these to a safe location for future use. If the access credentials are lost or compromised, you should regenerate the credentials from the service account page.

!!! note "Service account roles"
    Service accounts are created at the organization level, and may then become members of workspaces within the organization.
    
    A service account may only be a Member of an organization. It can never be an organization Admin. You may apply any valid _workspace-level_ role to a service account.