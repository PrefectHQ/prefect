---
description: Manage teams and organizations in Prefect Cloud.
tags:
    - UI
    - dashboard
    - Prefect Cloud
    - accounts
    - teams
    - workspaces
    - organizations
---

# Organizations in Prefect Cloud

For larger teams, and companies with more complex needs around user and access management, organizations provide several features that enable you to collaborate securely at scale, including:

- Organizational accounts and membership management.
- [Role Based Access Controls (RBAC)](/ui/roles/) to configure user permissions at organization and workspace levels.
- Service accounts to generate credentials for specific workloads.
- Expanded and customizable [Flow Run Retention Policy](/ui/flow-runs/#flow-run-retention-policy).


## Navigating organizations

You can see the organizations you're a member of, or create a new organization, by selecting the **Organizations** icon in the left navigation bar.

![Select the Organizations icon in Prefect Cloud.](/img/ui/organizations.png)

When you select an organization, you'll see an overview of the organization.

**Workspaces** shows you a list of workspaces within the organziation to which you have access.

## Organization members

**Members** shows you a list of users who are members of the organization. If you have been given the organization Admin role, you can invite new members and set organization roles for users here.

![Viewing the Organization member page in Prefect Cloud.](/img/ui/org-members.png)

Control granular access to workspaces by setting default access for all organization members, inviting specific members to collaborate in an organization workspace, or adding service account permissions.

### Inviting organization members

To invite new members to an organization in Prefect Cloud, select the **+** icon. Provide an email address and  organization role. You may add multiple email addresses.

![Invite new members to an organization in Prefect Cloud.](/img/ui/org-invite-members.png)

The user will receive an invite email with a confirmation link at the address provided. If the user does not already have a Prefect Cloud account, they must create an account before accessing the organization.

When the user accepts the invite, they become a member of your organization and are assigned the role from the invite. The member's role can be changed (or access removed entirely) by an organization Admin.

The maximum number of organization members varies. See the [Prefect Cloud plans](https://www.prefect.io/pricing) to learn more about options for supporting more users, service accounts, and workspaces.

## Service accounts

Service accounts enable you to create a Prefect Cloud API key that is not associated with a user account. Service accounts are typically used to configure API access for running agents or executing flow runs on remote infrastructure.

Select **Service Accounts** to view, create, or edit service accounts for your organization.

![Viewing service accoutns for an organization in Prefect Cloud.](/img/ui/service-accounts.png)

Service accounts are created at the organization level, but may be shared to individual workspaces within the organization. See [workspace sharing](#workspace-sharing) for more information.

!!! tip "Service account credentials"
    When you create a service account, Prefect Cloud creates a new API key for the account and provides the API configuration command for the execution environment. Save these to a safe location for future use. If the access credentials are lost or compromised, you should regenerate the credentials from the service account page.

## Workspace sharing

You may give organization members and service accounts access to workspaces within an organization. Each workspace within an organization may have its own members and service accounts with roles and permissions specific to that workspace. Organization Admins have full access to all workspaces in an organization.

Within a workspace, select **Workspace Sharing**, then select the **+** icon to add new members or service accounts to the workspace. Only organization Admins and workspace Owners may add members or service accounts to a workspace.

![Organization workspace sharing in Prefect Cloud.](/img/ui/org-workspace-sharing.png)

Members and service accounts must already be configured for the organization. An Admin or Owner may configure a different role for the user or service account as needed.

!!! note "Default workspace role"
    You may make a workspace available to anyone in an organization by settings a default role for "Anyone at...". Anyone in the organization may access the workspace with the specified default role permissions.

    The role given to users specifically added to the workspace overrides this setting.
    
    You may set this to No Access if you do not want organization members not specifically added to the workspace to access it (organization Admins excepted). 

## Organization and workspace roles

Prefect Cloud enables configuring both organization and workspace roles for users.

- Organization roles apply to users across an organization.
- Workspace roles apply to users within a specific workspace.

Select **Roles** within an organziation to see the configured roles for your organization. 

![Organization roles in Prefect Cloud.](/img/ui/org-roles.png)

Prefect Cloud provides default roles that cover most use cases. You may also create custom roles to suit your specific organization needs.

See [Roles (RBAC)](/ui/roles/) for details on default and custom role permissions.