# GraphQL API

Prefect Cloud exposes a full GraphQL API for querying and interacting with the system.

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
