# GraphQL API

Prefect Cloud exposes a full GraphQL API for querying and interacting with the system.

## GraphQL

GraphQL is a flexible query language. Most importantly for an infrastructure system like Prefect Cloud, it gives users the power to request exactly the information they require. You can think of a GraphQL query as representing the "keys" of a JSON document you'd like the server to provide values for.


## Authorization

In order to use the GraphQL API, you will need to authenticate and then use the `login` route to get a Prefect authorization token. This token should be included as the `Authorization` header on every request, with the format `Bearer <auth token>`.

## Queries

All Prefect Cloud data may be queried via GraphQL. See the interactive schema for complete details on available fields.

For example, the following query retrieves all flows whose names end with "flow"; the state of their most recent flow run; and the state history of five of that run's task runs, ordered alphabetically.

```graphql
query {
  flow(where: { name: { _ilike: "%flow" } }) {
    id
    name
    flow_run(order_by: { start_time: desc }, limit: 1) {
      id
      state
      task_run(limit: 5, order_by: { name: asc }) {
        states {
          timestamp
          state
        }
      }
    }
  }
}
```

## Mutations

In order to interact with Prefect Cloud, users can issue mutations. See the interactive schema for complete details on available fields.

Most sections of the concepts docs show examples of relevant mutations.

## Formatting

### IDs

All Prefect IDs are UUIDs and should be provided as strings.

#### Example:

```graphql
query {
  flow(where: { id: { _eq: "07786de2-7283-434f-a9b1-600044a8afb3" } }) {
    name
  }
}
```

### Dates & Times

Dates and times should be provided as ISO 8601-formatted strings. If no time zone information is included, UTC will be assumed.

#### Example:

```graphql
query {
  flow_run(where: { start_time: { _gt: "2019-01-01 12:00:00" } }) {
    id
    start_time
  }
}
```

### JSON

GraphQL has a difficult time parsing JSON inline, so we recommend providing any JSON values as GraphQL variables.

#### Example:

```graphql
mutation($state: JSON!) {
  setFlowRunState(
    input: {
      id: "61cab648-f09d-467d-b205-3892c8d55250"
      version: 1
      state: $state
    }
  ) {
    id
    start_time
  }
}
```

with variables:

```json
{
  "state": {
    "x": 1,
    "y": 2
  }
}
```
