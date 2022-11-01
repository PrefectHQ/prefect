---
description: Monitor user access and activity with Audit Logs in Prefect Cloud.
tags:
    - UI
    - dashboard
    - Prefect Cloud
    - enterprise
    - teams
    - workspaces
    - organizations
    - audit logs
    - compliance
---

# Audit Log <span class="badge cloud"></span> <span class="badge orgs"></span> <span class="badge enterprise"></span>

Prefect Cloud's [Organization and Enterprise plans](https://www.prefect.io/pricing) offer compliance and transparency functionality with Audit Log in Prefect Cloud 2. Audit logs provide a chronological record of activities performed by Prefect Cloud users in your organization, allowing you to monitor detailed Prefect Cloud actions for security and compliance purposes. 

Audit logs enable you to identify who took what action, when, and using what resources within your Prefect Cloud organization. In conjunction with appropriate tools and procedures, audit logs can assist in detecting potential security violations and investigating application errors.  

Audit logs can be used to identify changes in: 

- Access to workspaces
- User login activity
- API key creation 

See the [Prefect Cloud plans](https://www.prefect.io/pricing) to learn more about options for supporting audit logs.

## Viewing audit logs

Within your organization, select the **Audit Log** page to view audit logs. 

![Viewing audit logs for an organization in the Prefect Cloud UI.](/img/ui/audit-log.png)

Organization admins can view audit logs for: 

- Organization-level events in Prefect Cloud (for example, inviting a user, changing a user’s organization role, or deleting a service account).
- Workspace-level events in Prefect Cloud (for example, adding a user to a workspace, changing a user’s workspace role, or deleting a workspace).

Admins can filter audit logs on multiple dimensions to restrict the results they see by workspace, user, or event type.

Audit logs may also be filtered by date range. Audit log retention policy varies by [Prefect Cloud plan](https://www.prefect.io/pricing). See your [organization profile page](/ui/organizations/) for the current audit log retention period.

## Audit events

TK