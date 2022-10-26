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
    - service accounts
---

# Organizations <span class="badge cloud"></span> <span class="badge orgs"></span>

For larger teams or companies with more complex needs around user and access management, organizations in Prefect Cloud provide several features that enable you to collaborate securely at scale, including:

- [Organizational accounts and membership](#organization-members) management.
- [Role Based Access Controls (RBAC)](#organization-and-workspace-roles) to configure user permissions at organization and workspace levels.
- [Service accounts](#service-accounts) to generate credentials for specific workloads.
- Expanded and customizable [Flow Run Retention Policy](/ui/flow-runs/#flow-run-retention-policy).
- [Single Sign-on (SSO)](/ui/sso/) authentication using your identity provider (Enterprise plans).

See the [Prefect Cloud plans](https://www.prefect.io/pricing) to learn more about options for supporting more users, service accounts, and workspaces.

## Organizations overview

An organization is a type of account available on Prefect Cloud that enables more extensive and granular control over inviting workspace collaboration. Organizations are only available on Prefect Cloud.

Within an organization account you can:

- Invite members to join the organization.
- Give members administrator or member roles within the organization.
- Create service accounts that have credentials for non-user API access.
- Manage workspace access for all organization members.
- Add or remove member and service account access to workspaces.
- Assign workspace-specific roles and permissions to members and service accounts.

For example, you might create a workspace for a specific team. Within that workspace, give a developer member full Collaborator role access, and invite a data scientist with Read-only Collaborator permissions to monitor the status of scheduled and completed flow runs.

## Navigating organizations

You can see the organizations you're a member of, or create a new organization, by selecting the **Organizations** icon in the left navigation bar.

![Select the Organizations icon in Prefect Cloud.](/img/ui/organizations.png)

When you select an organization, the **Profile** page provides an overview of the organization.

- **Workspaces** enables you to access and manage workspaces within the organization.
- **Members** enables you to invite and manage users who are members of the organization.
- **Service Accounts** enables you to view, create, or edit service accounts for your organization.
- **Roles** enables you to view details for all workspace roles, and configure custom workspace roles with permission scopes for your organization.

## Organization workspaces

**Workspaces** shows you a list of [workspaces you can access within the organization](/ui/workspaces/). If you have been given the organization Admin role, you can create and manage workspaces here.

![Viewing the Organization workspaces page in Prefect Cloud.](/img/ui/org-workspaces.png)

You can also select the Prefect icon to see all workspaces you have been invited to access, across personal accounts and organizations.

## Organization members

**Members** shows you a list of users who are members of the organization. If you have been given the organization Admin role, you can invite new members and set organization roles for users here.

![Viewing the Organization member page in Prefect Cloud.](/img/ui/org-members.png)

You can control granular access to workspaces by setting default access for all organization members, inviting specific members to collaborate in an organization workspace, or adding service account permissions.

### Inviting organization members

To invite new members to an organization in Prefect Cloud, select the **+** icon. Provide an email address and  organization role. You may add multiple email addresses.

![Invite new members to an organization in Prefect Cloud.](/img/ui/org-invite-members.png)

The user will receive an invite email with a confirmation link at the address provided. If the user does not already have a Prefect Cloud account, they must create an account before accessing the organization.

When the user accepts the invite, they become a member of your organization and are assigned the role from the invite. The member's role can be changed (or access removed entirely) by an organization Admin.

The maximum number of organization members varies. See the [Prefect Cloud plans](https://www.prefect.io/pricing) to learn more about options for supporting more users, service accounts, and workspaces.

## Service accounts

[Service accounts](/ui/service-accounts/) enable you to create a Prefect Cloud API key that is not associated with a user account. Service accounts are typically used to configure API access for running agents or executing flow runs on remote infrastructure.

Select **Service Accounts** to view, create, or edit service accounts for your organization.

![Viewing service accoutns for an organization in Prefect Cloud.](/img/ui/service-accounts.png)

Service accounts are created at the organization level, but may be shared to individual workspaces within the organization. See [workspace sharing](#workspace-sharing) for more information.

!!! tip "Service account credentials"
    When you create a service account, Prefect Cloud creates a new API key for the account and provides the API configuration command for the execution environment. Save these to a safe location for future use. If the access credentials are lost or compromised, you should regenerate the credentials from the service account page.

!!! note "Service account roles"
    Service accounts are created at the organization level, and may then become members of workspaces within the organization.
    
    A service account may only be a Member of an organization. It can never be an organization Admin. You may apply any valid _workspace-level_ role to a service account.

See the [service accounts](/ui/service-accounts/) documentation for more information.

## Workspace sharing

[Workspace sharing](/ui/workspaces/#workspace-sharing) enables you to give organization members and service accounts access to workspaces within an organization. Each workspace within an organization may have its own members and service accounts with roles and permissions specific to that workspace. Organization Admins have full access to all workspaces in an organization.

Within a workspace, select **Workspace Sharing**, then select the **+** icon to add new members or service accounts to the workspace. Only organization Admins and workspace Owners may add members or service accounts to a workspace.

![Organization workspace sharing in Prefect Cloud.](/img/ui/org-workspace-sharing.png)

Members and service accounts must already be configured for the organization. An Admin or Owner may configure a different role for the user or service account as needed.

!!! note "Default workspace role"
    You may make a workspace available to any user in an organization by settings a default role for "Anyone at...". Users in the organization may access the workspace with the specified default role permissions. Default workspace roles do not apply to service accounts.

    The role given to users specifically added to the workspace is the union of workspace scopes given by the default workspace role and that users' role in the workspace.
    
    You may set this to "No Access" if you do not want organization members not specifically added to the workspace to access it (organization Admins excepted). 

See the [Workspace sharing](/ui/workspaces/#workspace-sharing) documentation for more information.

## Organization and workspace roles

Prefect Cloud enables you to configure both [organization and workspace roles](/ui/roles/) for users.

- Organization roles apply to users across an organization. These roles are Admin and Member.
- Workspace roles apply to users within a specific workspace.

Select **Roles** within an organziation to see the configured workspace roles for your organization. 

![Organization roles in Prefect Cloud.](/img/ui/org-roles.png)

Prefect Cloud provides default workspace roles that cover most use cases. You may also create custom workspace roles to suit your specific organization needs.

See the [Roles (RBAC)](/ui/roles/) documentation for more information on default and custom role permissions.

## Single Sign-on (SSO) <span class="badge enterprise"></span>

Prefect Cloud's [Organization and Enterprise plans](https://www.prefect.io/pricing) offer [single sign-on (SSO)](/ui/sso/) authentication integration with your team’s identity provider. SSO integration can bet set up with identity providers that support OIDC and SAML.

See the [Single Sign-on (SSO)](/ui/sso/) documentation for more information on default and custom role permissions.