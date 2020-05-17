# Projects

Projects are used to organize flows that have been registered with the Prefect API. Each flow is contained within a single project.

## Creating a project

### UI

Projects can be created from the project filter on the [dashboard](/orchestration/ui/dashboard) or the [project settings page](/orchestration/ui/team-settings.md#projects).

![](/orchestration/ui/team-projects.png)

### Prefect CLI

To create a new project with the Prefect CLI:

```
$ prefect create project "My Project"
```

### Core Client

To create a new project with the Core client:

```python
from prefect import Client

client = Client()
client.create_project(project_name="My Project")
```

### GraphQL <Badge text="GQL"/>

To create a new project with GraphQL, issue the following mutation:

```graphql
mutation {
  create_project(input: { name: "My Project" }) {
    project {
      id
      name
    }
  }
}
```

## Deleting a project

### UI

Projects can be deleted from the [project settings page](/orchestration/ui/team-settings.md#projects).

![](/orchestration/ui/team-projects.png)

### GraphQL <Badge text="GQL"/>

Deleting a project requires tenant admin permissions as well as the project's ID.

```graphql
mutation {
  delete_project(input: { project_id: "project-UUID" }) {
    success
  }
}
```

## Querying for projects <Badge text="GQL"/>

Viewing all projects by name, sorted by name:

```graphql
query {
  project(order_by: { name: asc }) {
    name
  }
}
```

Getting the id of a project with a specific name:

```graphql
query {
  project(where: { name: { _eq: "a name" } }) {
    id
  }
}
```
