# Role Based Access Controls <Badge text="Cloud"/>

Prefect Cloud has a rich feature set of role based access controls.

**Roles** are used to denote the permissions a user has as part of a team.

Roles can be assigned to both users and service accounts.

Standard plans come with basic role based access controls, which allows users to be assigned a pre-defined role.

Enterprise plans feature the ability to define and assign custom roles.

### Default Roles (Standard and Enterprise only)

Prefect Cloud contains three default roles

- Administrator
- User
- Read Only User

Default roles cannot be modified.

#### Administrators

Administrators have all permissions given to users, but are also able to actively manage their team in Prefect Cloud. This means they are able to invite new members, remove unwanted members, and change the roles of other members of their team.

#### Users

Users have permission to perform all actions required for daily use of Prefect Cloud; this includes registering new flows, kicking off flow runs, etc. They do not have permission to perform actions that impact other members of the team, meaning they cannot change the roles of their teammates, invite others to their tenant, etc.

#### Read Only Users

Restricted users are able to view all pages as a normal user would, but are unable to take any actions in Prefect Cloud. For example, they cannot create projects, kick off flow runs, etc. In essence, restricted users are read-only members of a team.

### Custom Roles (Enterprise Only)

To manage permissions more granularly, you can create new roles with custom sets of permissions. Custom roles are scoped to a team.

When creating or updating a role, users cannot grant the role more permissions than they possess.

Custom roles can be created, edited, and deleted on the [Roles page](https://cloud.prefect.io/team/roles).

Custom roles can also be created, edited, and deleted via the GraphQL API.

**Creating a new role**
```graphql
mutation {
  create_custom_role(input: { name : "my new role", permissions: ["read:flow"] }) {
    id
  }
}
```

**Updating a role's permissions**
Updating a role's permissions will change the permissions granted to all users and service accounts assigned that role.
```graphql
mutation {
  update_custom_role_permissions(input: { role_id : "76acc2c6-77b0-4461-9258-60c7021ffa4b", permissions: ["read:flow", "delete:flow"] }) {
    success
  }
}
```

**Deleting a role**
Please note: roles can only be deleted if they are not assigned to any current users/service accounts or invited users.
```graphql
mutation {
  delete_custom_role(input: { role_id : "76acc2c6-77b0-4461-9258-60c7021ffa4b" }) {
    success
  }
}
```


### Assigning Roles

Basic and custom roles can be assigned in the Prefect UI to [users](https://cloud.prefect.io/team/members) and [service accounts](https://cloud.prefect.io/team/service-accounts). When inviting a new user to your team, you can specify a role to assign them.

Roles can also be assigned programmatically via the GraphQL API.

```graphql
mutation {
  set_membership_role(input: { membership_id: "6c610b1b-db68-493c-9dd7-564974f822b0", role_id : "76acc2c6-77b0-4461-9258-60c7021ffa4b" }) {
    id
  }
}
```

When assigning a role to a user or service account, a user cannot assign a role that has more permissions than they possess.

### Querying for Role Information

To list available Default and Custom roles and their corresponding permissions, run the following query

```graphql
query {
  auth_role {
    created
    id
    name
    permissions
  }
}
```

The `id` value for a given role should be provided as the `role_id` parameter when calling `set_membership_role` or updating/deleting custom roles.

### Querying for Membership Information

To list all users and their membership ids in the current tenant, run the following query


```graphql
query {
  user_view_same_tenant {
    id
    account_type
    email
    first_name
    last_name
    username
    memberships {
      id
    }
  }
}
```

The `memberships.id` value for a given user should be provided as the `membership_id` parameter when calling `set_membership_role`.

### Audit Log (Enterprise Only)

Separately from task run or flow run logs, Prefect has an Enterprise-only feature to track “audit logs” for events within the system, per tenant. 

Audit logs for each tenant have a `timestamp`, a `message` describing the event, an `object_id` associated with an `object_table`, and an option `info`.

An example audit log for a user logging in would contain a timestamp, the login event message, the object table would be 'user' and the object id would be user id of the user logging in.


Audit logs can be accessed via the GraphQL API.

**Query the audit log**
```graphql
query {
  audit_log(order_by: {timestamp: descending}, limit:100) {
    object_id
    object_table
    timestamp
    message
  }
}
```
