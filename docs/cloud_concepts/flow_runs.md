# Flow Runs

Flow runs track the execution of a flow. They represent a discrete instantiation of the flow, with a specific set of parameters. There is no limit to the number of flow runs you can create, even if they start at the exact same time with the exact same parameters: Prefect supports unlimited concurrent execution.

## Creating a flow run

To create a flow run for a specific flow, issue the following GraphQL:

```graphql
mutation {
  createFlowRun(input: { flowId: "<flow id>" }) {
    id
    error
  }
}
```

## Scheduling a flow run

By default, flow runs are scheduled to start immediately. To run the flow in the future, simply pass a `scheduledStartTime` argument:

```graphql
mutation {
  createFlowRun(
    input: { flowId: "<flow id>", scheduledStartTime: "<start time>" }
  ) {
    id
    error
  }
}
```

## Updating flow run state

If you need to manually update the state of a flow run, you can do so by providing a new state at any time. You must also provide a "version" number. If the version number doesn't match the database, the update will fail.

::: State versioning
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
