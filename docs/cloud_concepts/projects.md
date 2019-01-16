# Projects

When flows are deployed to Prefect Cloud, they are organized into projects.

## Creating a new project

```graphql
mutation {
  createProject(input: { name: "My Project" }) {
    id
    error
  }
}
```
