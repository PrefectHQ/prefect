---
description: Workspaces are isolated environments for flows and deployments within Prefect Cloud.
tags:
    - UI
    - Prefect Cloud
    - workspaces
    - deployments
search:
  boost: 2
---

# Workspaces <span class="badge cloud"></span>

A workspace is a discrete environment within Prefect Cloud for your flows and deployments.
Workspaces are available to Prefect Cloud accounts only.

Workspaces can be used to organize and compartmentalize your workflows.
For example, you can use separate workspaces to isolate dev, staging, and prod environments, or to provide separation between different teams.

When you first log into Prefect Cloud, you will be prompted to create your own initial workspace.
After creating your workspace, you'll be able to view flow runs, flows, deployments, and other workspace-specific features in the Prefect Cloud UI.

![Viewing a workspace dashboard in the Prefect Cloud UI.](/img/ui/cloud-new-workspace.png)

Select a workspace name in the navigation menu to see all workspaces you can access.

![Viewing all available workspaces in the Prefect Cloud UI.](/img/ui/all-workspaces.png)

Your list of available workspaces may include:

- Your own account workspace.
- Workspaces in an account to which you've been invited and have been given access as an Admin or Member.

!!! cloud-ad "Workspace-specific features"
    Each workspace keeps track of its own:

    - [Flow runs](/ui/flow-runs/) and task runs executed in an environment that is [syncing with the workspace](/ui/cloud/#workspaces)
    - [Flows](/concepts/flows/) associated with flow runs or deployments observed by the Prefect Cloud API
    - [Deployments](/concepts/deployments/)
    - [Work pools](/concepts/work-pools/)
    - [Blocks](/ui/blocks/) and [Storage](/concepts/storage/)
    - [Automations](/concepts/automations/)

Your user permissions within workspaces may vary. [Account Admins](/ui/pro-enterprise/) can assign roles and permissions at the workspace level.

## Create a workspace

On the Account Workspaces dropdown or the **Workspaces** page select the **+** icon to create a new workspace.

You'll be prompted to configure:

- The **Workspace Owner** from the dropdown account menu options.
- The **Workspace Name** must be unique within the account.
- An optional description for the workspace.

![Creating a new workspace in the Prefect Cloud UI.](/img/ui/create-workspace.png)

Select **Create** to create the new workspace.
The number of available workspaces varies by [Prefect Cloud plan](https://www.prefect.io/pricing/).
See [Pricing](https://www.prefect.io/pricing/) if you need additional workspaces or users.

## Workspace settings

Within a workspace, select **Workspace Settings** to view or edit workspace details.  

![Managing a workspace in the Prefect Cloud UI.](/img/ui/workspace-settings.png)

The options menu enables you to edit workspace details or delete the workspace.

!!! warning "Deleting a workspace"
    Deleting a workspace deletes all deployments, flow run history, work pools, and notifications configured in workspace.

## Account membership

You can send an email invitation to invite a user to become a member of your account.

In your account select **Members**.
Any members will be listed with their handle, organizational role, and most recent login date.
On the **Invitiations** tab you'll see any previously invited individuals and information about the invitation status.

![Managing members in a workspace in the Prefect Cloud UI.](/img/ui/workspace-collaborators.png)

To invite a user to become an account member, select the **+** icon.
You'll be prompted for the email address of the person you'd like to invite.
Add the email address, then select **Send** to initiate the invitation.

If the user does not already have a Prefect Cloud account, they will be able to create one when accepting the invitation.

To delete a member from an account, select **Remove** from the menu on the left side of the user's information on this page.

## Workspace access <span class="badge pro"></span> <span class="badge enterprise"></span>

Within a Prefect Cloud account, Admins can invite other users and provision [service accounts](/ui/service-accounts/) to a workspace.
In addition to giving the user access to the workspace, the Admin assigns a [workspace role](/ui/roles/) to the user.
The role specifies the scope of permissions for the user within the workspace.

As an Admin in workspace, select **Workspaces** to manage individuals and service accounts for the workspace.
If you've previously invited other individuals and service accounts, you'll see them listed.

![Managing sharing in a workspace in the Prefect Cloud UI.](/img/ui/workspace-sharing.png)

To invite someone a workspace, select the Members **+** icon. You can select from a list of existing account members.

Select a Workspace Role for the user.
This will be the initial role for the user within the workspace. A workspace Owner can change this role at any time.

Select **Send** to initiate the invitation.

To add a service account to a workspace, select the Service Accounts **+** icon.
You can select from a list of existing service accounts configured for the organization.
Select a Workspace Role for the service account. This will be the initial role for the service account within the workspace.
A workspace Owner can change this role at any time. Select **Share** to finalize adding the service account.

To delete a workspace collaborator or service account, select **Remove** from the menu on the right side of the user or service account information on this page.

## Workspace transfer

Workspace transfer enables you to move an existing workspace from one account to another.
For example, you may transfer a workspace from a personal account to an organization.

Workspace transfer retains existing workspace configuration and flow run history, including blocks, deployments, notifications, work pools, and logs.

!!! note "Workspace transfer permissions"
    Workspace transfer must be initiated or approved by a user with admin privileges for the workspace to be transferred.

    For example, if you are transferring a personal workspace to an organization, the owner of the personal account is the default admin for that account and must initiate or approve the transfer.

    To initiate a workspace transfer between personal accounts, contact [support@prefect.io](mailto:support@prefect.io).

### Transfer a workspace

To transfer a workspace, select **Settings**  -> **General** within the workspace.
Then, from the three dot menu in the upper right of the page, select **Transfer**.

![Initiating a workspace transfer in the Prefect Cloud UI.](/img/ui/workspace-transfer.png)

The **Transfer Workspace** page shows the workspace to be transferred on the left.
Select the target account or organization for the workspace on the right.

!!! tip "Workspace transfer impact on accounts"
    Workspace transfer may impact resource usage and costs for source and target account or organization.

    When you transfer a workspace, users, API keys, and service accounts may lose access to the workspace. 
    Audit log will no longer track activity on the workspace. 
    Flow runs ending outside of the destination account’s flow run retention period will be removed. 
    You may also need to update Prefect CLI profiles and execution environment settings to access the workspace's new location.

    You may also incur new charges in the target account to accommodate the transferred workspace.

    The **Transfer Workspace** page outlines the impacts of transferring the selected workspace to the selected target. 
    Please review these notes carefully before selecting **Transfer** to transfer the workspace.
