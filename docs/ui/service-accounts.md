---
description: Workspaces are isolated environments for flows and deployments within Prefect Cloud.
tags:
    - UI
    - Prefect Cloud
    - workspaces
    - deployments
---

# Service Accounts <span class="badge cloud"></span> <span class="badge orgs"></span>

Service accounts enable you to create a Prefect Cloud API key that is not associated with a user account. Service accounts are typically used to configure API access for running agents or executing deployment flow runs on remote infrastructure.

## Service accounts overview

Service accounts are non-user organization accounts that have the following:

- Prefect Cloud [API keys](/ui/cloud-getting-started/#create-an-api-key)
- Organization [roles](/ui/roles/) and permissions

Using service account credentials, you can [configure an execution environment](/ui/cloud-getting-started/#configure-execution-environment) to interact with your Prefect Cloud organization workspaces without a user having to manually log in from that environment. Service accounts may be created, added to workspaces, have their roles changed, or deleted without affecting organization user accounts.

Select **Service Accounts** to view, create, or edit service accounts for your organization.

![Viewing service accounts for an organization in Prefect Cloud.](/img/ui/service-accounts.png)

Service accounts are created at the organization level, but individual workspaces within the organization may be shared with the account. See [workspace sharing](#workspace-sharing) for more information.

!!! tip "Service account credentials"
    When you create a service account, Prefect Cloud creates a new API key for the account and provides the API configuration command for the execution environment. Save these to a safe location for future use. If the access credentials are lost or compromised, you should regenerate the credentials from the service account page.

!!! note "Service account roles"
    Service accounts are created at the organization level, and may then become members of workspaces within the organization.
    
    A service account may only be a Member of an organization. It can never be an organization Admin. You may apply any valid _workspace-level_ role to a service account.

## Create a service account

Within your organization, on the **Service Accounts** page, select the **+** icon to create a new service account. You'll be prompted to configure:

- The service account name. This name must be unique within your account or organization.
- An expiration date, or the **Never Expire** option.

!!! note "Service account roles"
    A service account may only be a Member of an organization. You may apply any valid _workspace-level_ role to a service account when it is [added to a workspace](/ui/workspaces/#workspace-sharing).

Select **Create** to actually create the new service account. 

![Creating a new service account in the Prefect Cloud UI.](/img/ui/create-service-account.png)

Note that API keys cannot be revealed again in the UI after you generate them, so copy the key to a secure location.

You can change the API key and expiration for a service account by rotating the API key. Select **Rotate API Key** from the menu on the left side of the service account's information on this page. 

To delete a service account, select **Remove** from the menu on the left side of the service account's information.