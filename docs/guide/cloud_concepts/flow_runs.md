# Flow Runs

Flow runs track the execution of a flow. They represent a discrete instantiation of the flow, with a specific set of parameters. There is no limit to the number of flow runs you can create, even if they start at the exact same time with the exact same parameters: Prefect supports unlimited concurrent execution.

## Creating a flow run

To create a flow run for a specific flow, issue the following GraphQL:

```graphql
mutation {
  createFlowRun(input: { flowId: "<flow id>" }) {
    id
  }
}
```

### Idempotent run creation

If you provide an `idempotencyKey` when creating a flow run, you can safely attempt to recreate that run again without actually recreating it. This is helpful when you have a substandard network connection or when you're worried about redundancy in your run triggers. Idempotency is preserved for 24 hours, after which time a new run will be created for the same key. Each idempotent request refreshes the cache for an additional 24 hours.


```graphql
mutation {
  createFlowRun(input: { flowId: "<flow id>", idempotencyKey: "any-key" }) {
    id
  }
}
```

## Scheduling a flow run

By default, flow runs are scheduled to start immediately. To run the flow in the future, simply pass a `scheduledStartTime` argument:

```graphql
mutation {
  createFlowRun(
    input: { flowId: "<flow id>", scheduledStartTime: "<YYYY-MM-DD HH:MM:SS>" }
  ) {
      id
  }
}
```

## Updating flow run state

If you need to manually update the state of a flow run, you can do so by providing a new state at any time. You must also provide a "version" number. If the version number doesn't match the database, the update will fail.

::: tip State versioning
Prefect implements a form of optimistic locking for state updates. In order to update a state, you must provide a version number that matches the database. This proves to the system that you're working with the most up-to-date knowledge. If your version doesn't match, it means that someone or some process updated the state since the last time you checked it, and your knowledge is obsolete.
:::

1.  First, query for the current state version

```graphql
query {
  flow_run_by_pk(id: "<flow run id>") {
    version
  }
}
```

2. Next, update the state

```graphql
mutation($state: JSON!) {
  setFlowRunState(input: {flowRunId: "<flow run id>", version: <version>, state: $state}) {
      id
  }
}
```

with variables:

```json
{
    state: {
        type: "Success"
        message: "It worked!"
    }
}
```
