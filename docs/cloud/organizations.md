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
search:
  boost: 2
---

# Organizations <span class="badge cloud"></span> <span class="badge orgs"></span>

For larger teams or companies with more complex needs around user and access management, organizations in Prefect Cloud provide several features that enable you to collaborate securely at scale.

An organization is a type of account available on Prefect Cloud that enables more extensive and granular control over inviting workspace collaboration. Organizations are only available on Prefect Cloud.

![Organizations icon in Prefect Cloud.](/img/ui/organizations.png)

You can see the organizations you're a member of, or create a new organization, by clicking on the workspace name and selecting the gear icon next to the relevant organization.

When you select an organization, the **Organization** page provides an overview of the organization.

- [**Workspaces**](/cloud/workspaces/) enables you to access and manage workspaces within the organization.
- **Members** enables you to invite and manage users who are members of the organization, if you're an Admin.
- [**Audit Log**](/cloud/users/audit-log/) exists for Admins of Enterprise accounts only. Enables you to view a log of all actions taken by users in the organization.
- [**Service Accounts**](/cloud/users/service-accounts/) enables you to view, create, or edit service accounts for your organization.
- [**Roles**](/cloud/users/roles/) enables you to view details for all workspace roles, and configure custom workspace roles with permission scopes for your organization.
- [**SSO**](/cloud/users/sso/) Enables Admins to configure single sign-on (SSO) authentication using an identity provider.

## Organization members

You can control granular access to workspaces by setting default access for all organization members, inviting specific members to collaborate in an organization workspace, or adding service account permissions.

To invite new members to an organization in Prefect Cloud, select the **+** icon. Provide an email address and  organization role. You may add multiple email addresses.

![Invite new members to an organization in Prefect Cloud.](/img/ui/org-invite-members.png)

The user will receive an invite email with a confirmation link at the address provided. If the user does not already have a Prefect Cloud account, they must create an account before accessing the organization.

When the user accepts the invite, they become a member of your organization and are assigned the role from the invite. The member's role can be changed (or access removed entirely) by an organization Admin.

The maximum number of organization members varies. See the [Prefect Cloud plans](https://www.prefect.io/pricing) to learn more about options for supporting more users.

## Learn more

Learn more about organization features on the pages linked below.

- [Role Based Access Controls (RBAC)](/cloud/users/roles/) to configure user permissions at organization and workspace levels.
- [Service accounts](/cloud/users/service-accounts/) to generate credentials for specific workloads.
- [Expanded and customizable Flow Run Retention Policy](/ui/flow-runs/#flow-run-retention-policy).
- [Enhanced rate limits](/cloud/rate-limits/) for higher volume workloads.
- [Audit Logs](/cloud/users/audit-log/) for monitoring user actions (Enterprise plans).
- [Single Sign-on (SSO)](/cloud/users/sso/) authentication.
