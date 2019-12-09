# GraphQL API

Prefect Cloud exposes a full GraphQL API for querying and interacting with the platform.

We've designed this API to be clear and powerful. It is not merely a way to send instructions to Cloud; it allows users to fully introspect every piece of their relevant data.

Throughout these docs, sections directly related to the GraphQL API are denoted with a <Badge text="GQL" vertical="middle"/> badge.

## Queries

All Prefect Cloud data may be queried via GraphQL. You can view the interactive GraphQL schema browser for an API reference and complete details on available fields. In general, Cloud exposes a SQL-like interface for accessing data.

For example, the following query retrieves the id and name of all flows with names ending in "train", as well as the state of their most recent flow run:

```graphql
query {
  flow(where: { name: { _ilike: "%train" } }) {
    id
    name
    flow_run(order_by: { start_time: desc }, limit: 1) {
      id
      state
    }
  }
}
```

In this example, we retrieve the name, start time, and end time of the 5 task runs that failed
most recently:

```graphql
query {
  task_run(
    where: { state: { _eq: "Failed" } }
    order_by: { state_timestamp: desc }
    limit: 5
  ) {
    name
    start_time
    end_time
  }
}
```

## Mutations

In order to interact with Prefect Cloud, users can issue "mutations," which represent various actions. You can view the interactive GraphQL schema browser for an API reference and complete details on available fields.

Most sections of these concepts docs show examples of relevant mutations.

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
    "type": "Scheduled"
  }
}
```
