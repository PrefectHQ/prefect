---
description: Workspaces are isolated environments for flows and deployments within Prefect Cloud.
tags:
    - UI
    - Prefect Cloud
    - workspaces
    - deployments
---

# Workspaces <span class="badge cloud"></span>

A workspace is a discrete environment within Prefect Cloud for your flows and deployments. Workspaces are only available to Prefect Cloud accounts.

Workspaces could be used in any way you like to organize or compartmentalize your workflows. For example, you could use separate workspaces to isolate dev, staging, and prod environments, or to provide separation between different teams.

### Workspaces overview

When you first log into Prefect Cloud, you will be prompted to create your own initial workspace. After creating your workspace, you'll be able to view flow runs, flows, deployments, and other workspace-specific features in the Prefect Cloud UI.

![Viewing a workspace dashboard in the Prefect Cloud UI.](/img/ui/cloud-new-workspace.png)

Select the **Workspaces Icon** to see all of the workspaces you can access. 

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

## Create a workspace

On the **Workspaces** page, select the **+** icon to create a new workspace. You'll be prompted to configure:

- The workspace owner &mdash; the user account or organization managing the workspace.
- A handle, or name, for the workspace. This name must be unique within your account or organization.
- An optional description for the workspace.

![Creating a new workspace in the Prefect Cloud UI.](/img/ui/create-workspace.png)

Select **Create** to actually create the new workspace. The number of available workspaces varies by [Prefect Cloud plan](https://www.prefect.io/pricing/). See [Pricing](https://www.prefect.io/pricing/) if you need additional workspaces or users. 

## Workspace settings

Within a workspace, select **Workspace Settings** to view or edit workspace details.  

![Managing a workspace in the Prefect Cloud UI.](/img/ui/workspace-settings.png)

This page enables you to copy the configuration string to [set up a local development or execution environment](/ui/cloud-getting-started/#configure-execution-environment) to work this workspace.

The options menu enables you to edit workspace details or delete the workspace.

!!! warning "Deleting a workspace"
    Deleting a workspace deletes all deployments, flow run history, work queues, and notifications configured in workspace.

## Workspace collaborators

Personal account users may invite _workspace collaborators_, users who can join, view, and run flows in your workspaces.

In your workspace, select **Workspace Collaborators**. If you've previously invited collaborators, you'll see them listed.

![Managing collaborators in a workspace in the Prefect Cloud UI.](/img/ui/workspace-collaborators.png)

To invite a user to become a workspace collaborator, select the **+** icon. You'll be prompted for the email address of the person you'd like to invite. Add the email address, then select **Send** to initiate the invitation. 

If the user does not already have a Prefect Cloud account, they will be able to create one when accepting the workspace collaborator invitation.

To delete a workspace collaborator, select **Remove** from the menu on the left side of the user's information on this page.

## Workspace sharing <span class="badge orgs"></span>

Within a Prefect Cloud [organization](/ui/organizations/), Admins and workspace Owners may invite users and [service accounts](/ui/service-accounts/) to work in an organization workspace. In addition to giving the user access to the workspace, the Admin or Owner assigns a [workspace role](/ui/roles/) to the user. The role specifies the scope of permissions for the user within the workspace.

In an organization workspace, select **Workspace Sharing** to manage users and service accounts for the workspace. If you've previously invited users and service accounts, you'll see them listed.

![Managing sharing in a workspace in the Prefect Cloud UI.](/img/ui/workspace-sharing.png)

To invite a user to become a workspace collaborator, select the Members **+** icon. You can select from a list of existing organization members. 

Select a Workspace Role for the user. This will be the initial role for the user within the workspace. A workspace Owner can change this role at any time.

Select **Send** to initiate the invitation. 

To add a service account to a workspace, select the Service Accounts **+** icon. You can select from a list of existing service accounts configured for the organization. Select a Workspace Role for the service account. This will be the initial role for the service account within the workspace. A workspace Owner can change this role at any time. Select **Share** to finalize adding the service account.

To delete a workspace collaborator or service account, select **Remove** from the menu on the right side of the user or service account information on this page.