# Setting flow run states

Sometimes, it's useful to update a flow run state manually.

### UI

To manually set a flow run state from the UI, visit the [flow run page](/orchestration/ui/flowrun).

![](/orchestration/ui/flowrun-mark-as.png)

### GraphQL <Badge text="GQL"/>

If you need to manually update the state of a flow run, you can do so by providing a new state at any time. You must also provide a "version" number. If the version number doesn't match the database, the update will fail.

::: tip State versions
Prefect implements a form of optimistic locking for state updates. In order to update a state, you must provide a version number that matches the current version. This proves to the system that you're working with the most up-to-date knowledge. If your version doesn't match, it means that someone or some process updated the state since the last time you checked it, and the update will fail.
:::

First, query for the current state version:

```graphql
query {
  flow_run_by_pk(id: "<flow run id>") {
    version
  }
}
```

Next, update the state:

```graphql
mutation($state: JSON!) {
  set_flow_run_state(input: {flow_run_id: "<flow run id>", version: <version>, state: $state}) {
      id
  }
}
```

with variables:

```json
// GraphQL variables
{
    state: {
        type: "Success"
        message: "It worked!"
    }
}
```
