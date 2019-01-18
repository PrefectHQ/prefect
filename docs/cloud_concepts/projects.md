# Projects

When flows are deployed to Prefect Cloud, they are organized into projects.

## Querying for projects

Viewing all projects by name and id:

```graphql
query {
  project(order_by: { name: asc }) {
    id
    name
  }
}
```

Getting the id of a project with a specific name:

````graphql
query {
    project(where: { name: { _eq: "a name" } }) {
        id
        name
    }
}

## Creating a new project

```graphql
mutation {
  createProject(input: { name: "My Project" }) {
    id
    error
  }
}
````
