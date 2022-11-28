---
description: Configure user workspace roles in Prefect Cloud.
tags:
    - UI
    - dashboard
    - Prefect Cloud
    - accounts
    - teams
    - workspaces
    - organizations
    - custom roles
    - RBAC
---

# User and Service Account Roles <span class="badge cloud"></span> <span class="badge orgs"></span>

[Organizations](/ui/organizations/) in Prefect Cloud let you give people in your organization access to the appropriate Prefect functionality within your organization and within specific workspaces. 

Role-based access control (RBAC) functionality in Prefect Cloud enables you to assign users granular permissions to perform certain activities within an organization or a workspace.  

To give users access to functionality beyond the scope of Prefect’s built-in workspace roles, you may also create custom roles for users.


## Built-in roles

Roles give users abilities at either the organization level or at the individual workspace level. 

- An _organization-level role_ defines a user's default permissions within an organization. 
- A _workspace-level role_ defines a user's permissions within a specific workspace.

The following sections outline the abilities of the built-in, Prefect-defined organizational and workspace roles.

### Organization-level roles

The following built-in roles have permissions across an organization in Prefect Cloud.

| Role | Abilities |
| --- | --- |
| Admin | &bull; Set/change all organization profile settings allowed to be set/changed by a Prefect user. <br> &bull; Add and remove organization members, and their organization roles. <br> &bull; Create and delete service accounts in the organization. <br> &bull; Create workspaces in the organization. <br> &bull; Implicit workspace owner access on all workspaces in the organization. |
| Member | &bull; View organization profile settings. <br> &bull; View workspaces I have access to in the organization. <br> &bull; View organization members and their roles. <br> &bull; View service accounts in the organization. |

### Workspace-level roles

The following built-in roles have permissions within a given workspace in Prefect Cloud.

| Role | Abilities |
| --- | --- |
| Owner | &bull; Run flows. <br> &bull; View and delete flow runs within a workspace. <br> &bull; Create, view, edit, and delete deployments within a workspace. <br> &bull; Create, view, edit, and delete work queues within a workspace. <br> &bull; Create, view, edit, and delete blocks within a workspace. <br> &bull; Create, view, edit, and delete notifications within a workspace. <br> &bull; Add and remove organization members, and set their role within a workspace. <br> &bull; Set the workspace’s default workspace role for all users in the organization. <br> &bull; Set, view, edit workspace settings. |
| Collaborator | &bull; Run flows within a workspace. <br> &bull; View and delete flow runs within a workspace. <br> &bull; Create, view, edit, and delete deployments within a workspace. <br> &bull; Create, view, edit, and delete work queues within a workspace. <br> &bull; Create, view, edit, and delete all blocks within a workspace. <br> &bull; Create, view, edit, and delete notifications within a workspace. <br> &bull; View workspace setting within a workspace. |
| Read-only collaborator | &bull; View flow runs within a workspace. <br> &bull; View deployments within a workspace. <br> &bull; View all Work Queues. <br> &bull; View all Blocks. <br> &bull; View all Notifications. <br> &bull; View workspace settings (handle & description currently). |

## Custom workspace roles

The built-in roles will serve the needs of most users, but your team may need to configure custom roles, giving users access to specific permissions within a workspace.

Custom roles can inherit permissions from a built-in role. This enables tweaks to meet your organization’s needs, while ensuring users can still benefit from Prefect’s default workspace role permission curation as new functionality becomes available.

Custom workspace roles can also be created independent of Prefect’s built-in roles. This option gives workspace admins full control of user access to workspace functionality. However, for non-inherited custom roles, the workspace admin takes on the responsibility for monitoring and setting permisssions for new functionality as it is released.

See [Role permissions](#workspace-role-permissions) for details of permissions you may set for custom roles.

After you create a new role, it become available in the organization **Members** page and the **Workspace Sharing** page for you to apply to users.

### Inherited roles

A custom role may be configured as an **Inherited Role**. Using an inherited role allows you to create a custom role using a set of initial permissions associated with a built-in Prefect role. Additional permissions can be added to the custom role. Permissions included in the inherited role cannot be removed.

Custom roles created using an inherited role will follow Prefect's default workspace role permission curation as new functionality becomes available.

To configure an inherited role when configuring a custom role, select the **Inherit permission from a default role** check box, then select the role from which the new role should inherit permissions.

![Creating a custom role for a workspace using inherited permissions in Prefect Cloud](/img/ui/org-inherited-role.png)

## Workspace role permissions

The following permissions are available for custom roles.

### Blocks

| Permission | Description |
| --- | --- |
| View blocks | User can see configured blocks within a workspace. |
| Create, edit, and delete blocks | User can create, edit, and delete blocks within a workspace. Includes permissions of **View blocks**. |

### Deployments

| Permission | Description |
| --- | --- |
| View deployments | User can see configured deployments within a workspace. |
| Run deployments | User can run deployments within a workspace. This does not give a user permission to execute the flow associated with the deployment. This only gives a user (via their key) the ability to run a deployment &mdash; another user/key must actually execute that flow, such as a service account with an appropriate role. Includes permissions of **View deployments**. |
| Create and edit deployments | User can create and edit deployments within a workspace. Includes permissions of **View deployments** and **Run deployments**. |
| Delete deployments | User can delete deployments within a workspace. Includes permissions of **View deployments**, **Run deployments**, and **Create and edit deployments**. |

### Flows

| Permission | Description |
| --- | --- |
| View flows and flow runs  | User can see flows and flow runs within a workspace. |
| Create, update, and delete saved search filters | User can create, update, and delete saved flow run search filters configured within a workspace. Includes permissions of **View flows and flow runs**. |
| Create, update, and run flows | User can create, update, and run flows within a workspace. Includes permissions of **View flows and flow runs**. |
| Delete flows | User can delete flows within a workspace. Includes permissions of **View flows and flow runs** and **Create, update, and run flows**. |

### Notifications

| Permission | Description |
| --- | --- |
| View notification policies | User can see notification policies configured within a workspace. |
| Create and edit notification policies | User can create and edit notification policies configured within a workspace. Includes permissions of **View notification policies**. |
| Delete notification policies | User can delete notification policies configured within a workspace. Includes permissions of **View notification policies** and **Create and edit notification policies**. |

### Task run concurrency

| Permission | Description |
| --- | --- |
| View concurrency limits | User can see configured task run concurrency limits within a workspace. |		
| Create, edit, and delete concurrency limits | User can create, edit, and delete task run concurrency limits within a workspace. Includes permissions of **View concurrency limits**. |		

### Work queues

| Permission | Description |
| --- | --- |
| View work queues | User can see work queues configured within a workspace. |
| Create, edit, and pause work queues | User can create, edit, and pause work queues configured within a workspace. Includes permissions of **View work queues**. |
| Delete work queues | User can delete work queues configured within a workspace. Includes permissions of **View work queues** and **Create, edit, and pause work queues**. |

### Workspace management

| Permission | Description |
| --- | --- |
| View information about workspace service accounts | User can see service accounts configured within a workspace. |
| View information about workspace users | User can see user accounts for users invited to the workspace. |
| View workspace settings | User can see settings configured within a workspace. |
| Edit workspace settings | User can edit settings for a workspace. Includes permissions of **View workspace settings**. |
| Delete the workspace | User can delete a workspace. Includes permissions of **View workspace settings** and **Edit workspace settings**. |
