# Creating flow runs

If you're looking for documentation on how to set up a _schedule_ that creates a flow run repeatedly, see the [scheduling documentation](./scheduling.md)

If you're looking for documentation on how to run a flow from the UI, see the [UI documentation](../ui/flow_run.md#creation)

## CLI

Flow runs can be created using the `prefect run` command in the CLI. To create a flow run, the associated flow must be registered with the backend. You can lookup the flow in the backend by:

- `--id`: The UUID identifying the flow or flow group
- `--name`: The name of the flow; if not unique you will need to provide `--project` as well

```bash
$ prefect run --name "hello-world"
```

By default, this command will create a flow run and return immediately. An agent will then detect the flow run and submit it for execution. Often, it's nice to watch the flow run execute. The `--watch` flag will continuously poll the Prefect backend for the state of the flow run and display flow run logs.

```bash
$ prefect run --name "hello-world" --watch
```

See `prefect run --help` or [optional settings](#optional-settings) for additional flags that can be passed.

::: tip Local flow runs
`prefect run` can be used to execute a local flow as well if you provide a `--path` or a `--module` to load the flow from
:::

## Prefect library

```python
from prefect.backend.client import Client

client = Client()
client.create_flow_run(flow_id="d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7")
```

See [optional settings](#optional-settings) for additional information that can be passed.

## GraphQL  <Badge text="GQL"/>

To create a flow run for a specific flow, the `create_flow_run` mutation can be called:

```graphql
mutation {
  create_flow_run(input: { flow_id: "d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7" }) {
    id
  }
}
```

See [optional settings](#optional-settings) for additional options that can be passed.

## Optional settings

### Parameters

A flow run can be provided new parameters.

:::: tabs

::: tab CLI
```bash
$ prefect run --id "d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7" --param a=2
```
:::

::: tab Prefect library
```python
client.create_flow_run(
    flow_id="d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7", 
    parameters={"a": 2}
)
```
:::

::: tab GraphQL API
```graphql
mutation {
  create_flow_run(input: { 
  flow_id: "d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7", 
  parameters: "{\"a\": 2}" 
  }) {
    id
  }
}
```
:::

::::

### Flow run names

By default, a flow run is given an automatically generated name. However, a custom run name can be passed.

:::: tabs

::: tab CLI
```bash
$ prefect run --id "d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7" --run-name "docs example hello-world"
```
:::

::: tab Prefect library
```python
client.create_flow_run(
    flow_id="d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7", 
    flow_run_name="docs example hello-world"
)
```
:::

::: tab GraphQL API
```graphql
mutation {
  create_flow_run(input: { 
  flow_id: "d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7", 
  flow_run_name="docs example hello-world",
}
```
:::

::::

### Start times

Flows can be assigned a start time in the future rather than being marked for execution immediately.

:::: tabs

::: tab Prefect library
```python
client.create_flow_run(
    flow_id="d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7", 
    scheduled_start_time=pendulum.now().add(minutes=10)
)
```
:::

::: tab GraphQL API
```graphql
mutation {
  create_flow_run(input: { 
  flow_id: "d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7", 
  scheduled_start_time: "2021-05-07T15:09:16.815228-05:00" 
  }) {
    id
  }
}
```
:::

::::

::: tip Generating time strings for GraphQL
GraphQL expects ISO formatted datetime strings. This is default when you cast a `pendulum.DateTime` to a string. You can also explicitly call the conversion `pendulum.now().isoformat()` in newer versions of `pendulum`.
:::

### Idempotency

If you provide an `idempotency_key` when creating a flow run, you can safely attempt to recreate that run again without actually recreating it. This is helpful when you have a substandard network connection or when you're worried about redundancy in your run triggers. Idempotency is preserved for 24 hours, after which time a new run will be created for the same key. Each idempotent request refreshes the cache for an additional 24 hours.

:::: tabs

::: tab Prefect library
```python
client.create_flow_run(
    flow_id="d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7", 
    idempotency_key="do-not-create-two-runs"
)
```
:::

::: tab GraphQL API
```graphql
mutation {
  create_flow_run(input: { flow_id: "d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7", idempotency_key: "any-key" }) {
    id
  }
}
```
:::

::::


### Flow groups vs flows

For flows which update regularly, you can provide a `flow_group_id` instead of a `flow_id`. If provided, the unique unarchived flow within the flow group will be scheduled for execution.
