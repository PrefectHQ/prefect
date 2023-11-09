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
    - Pro
    - Enterprise
search:
  boost: 2
---

# Pro and Enterprise tier features<span class="badge cloud"></span> <span class="badge pro"></span> <span class="badge enterprise"></span>

For larger teams or companies with user and access management needs, Pro and Enterprise tiers provide features that enable you to collaborate securely at scale.

You can see the accounts you're a member of by clicking on the account name or account with workspace name and selecting the gear icon next to the relevant account.

![Select account from dropdown in Prefect Cloud.](/img/ui/select-account.png)

When you select an account, the **Account** page provides an overview of that account.

- [**Workspaces**](/cloud/workspaces/) enables you to access and manage workspaces within the organization.
- [**Audit Log**](/cloud/users/audit-log/) exists for Owners TK of Enterprise accounts only. Enables you to view a log of all actions taken by users in the organization.
- **Members** enables you to invite and manage users who are members of the organization, if you're an Admin.
- [**Service Accounts**](/cloud/users/service-accounts/) enables you to view, create, or edit service accounts for your organization.
- [**Teams**](/cloud/users/teams/) offers team management to simplify access control governance.
- [**Roles**](/cloud/users/roles/) (RBAC) enables you to view details for all workspace roles, and configure custom workspace roles with permission scopes for your organization.
- [**SSO**](/cloud/users/sso/) Enables Admins to configure single sign-on (SSO) authentication using an identity provider.
- **Billing** Provides information about your plan and payment method.
- **Settings** Allows you to control account settings such as enabling Marvin AI powered error summaries.

## Account members

You can control granular access to workspaces by setting default access for all account members, inviting specific members to collaborate in a workspace, or adding service account permissions.

To invite new members to an account in Prefect Cloud, select the **+** icon.
Provide an email address and account role (Admin or Member).
You may add multiple email addresses.

![Invite new members to an account in Prefect Cloud.](/img/ui/org-invite-members.png)

The user will receive an invite email with a confirmation link at the address provided.
If the user does not already have a Prefect Cloud account, they must create one before accessing the account they have been invited to join.

When the user accepts the invite, they become a member of that account and are assigned the role from the invite.
The member's role can be changed (or access removed entirely) by an account Admin.

The maximum number of organization members varies. See the [Prefect Cloud plans](https://www.prefect.io/pricing) to learn more about options for supporting more users.

## Learn more

Learn more about Pro and Enterprise features on the pages linked below.

- [Role Based Access Controls (RBAC)](/cloud/users/roles/) to configure user permissions at organization and workspace levels.
- [Service accounts](/cloud/users/service-accounts/) to generate credentials for specific workloads.
- [**SSO**](/cloud/users/sso/) single sign on.
- [Expanded and customizable Flow Run Retention Policy](/ui/flow-runs/#flow-run-retention-policy).
- [Single Sign-on (SSO)](/cloud/users/sso/) authentication.
- [Audit Logs](/cloud/users/audit-log/) for monitoring user actions (Enterprise plans).
- [Enhanced rate limits](/cloud/rate-limits/) for higher volume workloads.
- [Teams]
