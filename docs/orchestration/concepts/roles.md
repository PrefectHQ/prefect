# Roles <Badge text="Cloud"/>

User roles are used to denote the permissions a user has as part of a team. There are currently three roles: users, restricted users, and administrators.

### Users

Users have permission to perform all actions required for daily use of Prefect Cloud; this includes registering new flows, kicking off flow runs, etc. They do not have permission to perform actions that impact other members of the team, meaning they cannot change the roles of their teammates, invite others to their tenant, etc.

### Restricted Users

Restricted users are able to view all pages as a normal user would, but are unable to take any actions in Prefect Cloud. For example, they cannot create projects, kick off flow runs, etc. In essence, restricted users are read-only members of a team.

### Administrators

Administrators have all permissions given to users, but are also able to actively manage their team in Prefect Cloud. This means they are able to invite new members, remove unwanted members, and change the roles of other members of their team.
