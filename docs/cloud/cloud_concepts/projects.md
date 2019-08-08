# Projects

Projects are used to organize flows that have been deployed to Prefect Cloud. Each flow is contained within a single project.

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

## Creating a new project <Badge text="GQL"/>

```graphql
mutation {
  createProject(input: { name: "My Project" }) {
    project {
        id
        name
    }
  }
}
```
