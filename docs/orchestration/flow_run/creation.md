# Creating flow runs

If you're looking for documentation on how to set up a _schedule_ that creates a flow run repeatedly, see the [scheduling documentation](./scheduling.md)

If you're looking for documentation on how to run a flow from the API, see the [UI documentation](../ui/flow_run.md#creation)

## CLI

Flow runs can be created using the `prefect run` command in the CLI. To create a flow run, the associated flow must be registered with the backend. You can lookup the flow in the backend by:

- `--id`: The UUID identifying the flow or flow group
- `--name`: The name of the flow

```bash
$ prefect run --name "my flow"
```

See [optional settings](#optional-settings) for additional flags that can be passed.

## Prefect library

```python
from prefect.backend.client import Client

client = Client()
client.create_flow_run(flow_id="<flow-id>")
```

See [optional settings](#optional-settings) for additional information that can be passed.

## GraphQL  <Badge text="GQL"/>

To create a flow run for a specific flow, the `create_flow_run` mutation can be called:

```graphql
mutation {
  create_flow_run(input: { flow_id: "<flow-id>" }) {
    id
  }
}
```

See [optional settings](#optional-settings) for additional options that can be passed.

## Optional settings

### Flow groups vs flows

For flows which update regularly, you can provide a `flow_group_id` to `create_flow_run` instead of a `flow_id`. If provided, the unique unarchived flow within the flow group will be scheduled for execution.

### Parameters

A flow run can be provided new parameters.

```bash
$ prefect run --id "<flow-id>" --param a=2
```

```python
client.create_flow_run(flow_id="<flow-id>", parameters={"a": 2})
```

```graphql
mutation {
  create_flow_run(input: { 
  flow_id: "<flow-id>", 
  parameters: "{\"a\": 2}" 
  }) {
    id
  }
}
```

### Start times

Flows can be assigned a start time in the future rather than being marked for execution immediately.

```python
client.create_flow_run(flow_id="<flow-id>", scheduled_start_time=pendulum.now().add(minutes=10))
```

```graphql
mutation {
  create_flow_run(input: { 
  flow_id: "<flow-id>", 
  scheduled_start_time: "2021-05-07T15:09:16.815228-05:00" 
  }) {
    id
  }
}
```

::: tip Generating time strings in GraphQL
GraphQL expects ISO formatted datetime strings. This is default when you cast a `pendulum.DateTime` to a string. You can also explicitly call the conversion `pendulum.now().isoformat()` in newer versions of `pendulum`.
:::

### Idempotency

If you provide an `idempotency_key` when creating a flow run, you can safely attempt to recreate that run again without actually recreating it. This is helpful when you have a substandard network connection or when you're worried about redundancy in your run triggers. Idempotency is preserved for 24 hours, after which time a new run will be created for the same key. Each idempotent request refreshes the cache for an additional 24 hours.

```python
client.create_flow_run(flow_id="<flow-id>", idempotency_key="do-not-create-two-runs")
```

```graphql
mutation {
  create_flow_run(input: { flow_id: "<flow-id>", idempotency_key: "any-key" }) {
    id
  }
}
```

