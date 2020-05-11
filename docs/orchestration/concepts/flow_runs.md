# Flow Runs

Flow runs track the execution of a flow. They represent a discrete instantiation of the flow, with a specific set of parameters. There is no limit to the number of flow runs you can create, even if they start at the exact same time with the exact same parameters: Prefect supports unlimited concurrent execution.

## Creating a flow run

### UI

To create a flow run from the UI, visit the [flow page](/orchestration/ui/flow.html#run) and click "Run Flow".

![](/orchestration/ui/flow-run.png)

### Core Client

To create a flow run for a specific flow with the Core client:

```python
client.create_flow_run(flow_id="<flow id>")
```

The client method takes a number of optional arguments, including scheduled start time, parameters and an idempotency key. See the API reference for complete detail.

::: tip A Stable API for Flow Runs
For flows which update regularly, you can instead provide a `version_group_id` to `create_flow_run`. If provided, the unique unarchived flow within the version group will be scheduled for execution.
:::

### Core CLI

You can also create flow runs via the Prefect CLI by providing a flow name and its corresponding project name if using Cloud:

```bash
# Using Prefect Core's server
prefect run server --name "My Flow Name"
```

```bash
# Using Prefect Cloud
prefect run cloud --name "My Flow Name" --project "Hello, World!"
```

Similarly to the Client call, you can optionally provide parameters here as well.

### GraphQL <Badge text="GQL"/>

To create a flow run for a specific flow, issue the following GraphQL:

```graphql
mutation {
  create_flow_run(input: { flow_id: "<flow id>" }) {
    id
  }
}
```

As with the Core Client, you can instead provide `version_group_id` as an input to schedule a run for the unique unarchived flow within the provided version group. This provides a stable API for running flows which are regularly updated.

### Idempotent run creation <Badge text="GQL"/>

If you provide an `idempotency_key` when creating a flow run, you can safely attempt to recreate that run again without actually recreating it. This is helpful when you have a substandard network connection or when you're worried about redundancy in your run triggers. Idempotency is preserved for 24 hours, after which time a new run will be created for the same key. Each idempotent request refreshes the cache for an additional 24 hours.

```graphql
mutation {
  create_flow_run(input: { flow_id: "<flow id>", idempotency_key: "any-key" }) {
    id
  }
}
```

## Scheduling a flow run <Badge text="GQL"/>

By default, flow runs are scheduled to start immediately. To run the flow in the future, pass a `scheduled_start_time` argument:

```graphql
mutation {
  create_flow_run(
    input: {
      flow_id: "<flow id>"
      scheduled_start_time: "<YYYY-MM-DD HH:MM:SS>"
    }
  ) {
    id
  }
}
```

## Updating flow run state

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
