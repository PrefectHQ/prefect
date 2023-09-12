---
description: Restrict Block and Deployment access to individual actors within a workspace. 
tags:
    - UI
    - Permissions
    - Access
    - Prefect Cloud
    - enterprise
    - teams
    - workspaces
    - organizations
    - audit logs
    - compliance
search:
  boost: 2
---

# Object Access Control Lists <span class="badge cloud"></span></span> <span class="badge enterprise"></span>

Prefect Cloud's [Enterprise plan](https://www.prefect.io/pricing) offers object-level access control lists to restrict access to specific users and service accounts within a workspace. ACLs are supported for blocks and deployments.

Organization Admins and Workspace Owners can configure access control lists by navigating to an object and clicking **manage access**. When an ACL is added, all users and service accounts with access to an object via their workspace role will lose access if not explicitly added to the ACL.

![Viewing ACL for a deployment in the Prefect Cloud UI.](/img/ui/access-control.png)


See the [Prefect Cloud plans](https://www.prefect.io/pricing) to learn more about options for supporting object-level access control.

