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

## Creating a new project

#### Prefect CLI

To create a new project with the Prefect CLI:

```
$ prefect create project "My Project"
```

#### Core Client

To create a new project with the Core client:

```python
from prefect import Client

client = Client()
client.create_project(project_name="My Project")
```

#### GraphQL <Badge text="GQL"/>

To create a new project with GraphQL, issue the following mutation:

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

## Deleting a project

#### GraphQL <Badge text="GQL"/>

Deleting a project requires tenant admin permissions as well as the project's ID.
```graphql
mutation{
  deleteProject(input: {projectId: "project-UUID"}){
    success
  }
}
```
