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

### Parameters

A flow run can be provided new parameters.

:::: tabs

::: tab CLI
```bash
$ prefect run --id "<flow-id>" --param a=2
```
:::

::: tab Prefect library
```python
client.create_flow_run(
    flow_id="<flow-id>", 
    parameters={"a": 2}
)
```
:::

::: tab GraphQL API
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
:::

::::

### Flow run names

By default, a flow run is given an automatically generated name. However, a custom run name can be passed.

:::: tabs

::: tab CLI
```bash
$ prefect run --id "<flow-id>" --run-name "docs example hello-world"
```
:::

::: tab Prefect library
```python
client.create_flow_run(
    flow_id="<flow-id>", 
    flow_run_name="docs example hello-world"
)
```
:::

::: tab GraphQL API
```graphql
mutation {
  create_flow_run(input: { 
  flow_id: "<flow-id>", 
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
    flow_id="<flow-id>", 
    scheduled_start_time=pendulum.now().add(minutes=10)
)
```
:::

::: tab GraphQL API
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
:::

::::

::: tip Generating time strings for GraphQL
GraphQL expects ISO formatted datetime strings. This is default when you cast a `pendulum.DateTime` to a string. You can also explicitly call the conversion `pendulum.now().isoformat()` in newer versions of `pendulum`.
:::

### Agentless execution

Sometimes you'll want to run your flow without setting up an agent. You can run the flow locally with the `--local` CLI flag or `flow.run()` but then you lose features only available with the Prefect backend and can't view your flow run in the UI. 

The CLI provides an agentless execution mode with the `--execute` flag. This indicates that the flow should be executed locally instead of being submitted to an agent but the run will still be reported to the Prefect backend.

```bash
$ prefect run --name "hello-world" --execute
```

::: warning Run configuration and environments
When running your flow with agentless execution, we will ignore some flow configuration values. For example, if your flow has a `DockerRun` config, an agent would create a container for your flow to execute in, but agentless execution expects the flow to be in a valid environment already and will not create a container. Agentless execution will _always_ run your flow in the current process and will not create infrastructure for the flow run.

The following run configuration settings are retained:
- Environment variables
:::

::: warning Exiting during agentless execution
If you exit the process running the flow (i.e. with Ctrl-C), the flow run will be cancelled.
:::

This mode of flow run execution is currently only available via the CLI.

### Idempotency

If you provide an `idempotency_key` when creating a flow run, you can safely attempt to recreate that run again without actually recreating it. This is helpful when you have a substandard network connection or when you're worried about redundancy in your run triggers. Idempotency is preserved for 24 hours, after which time a new run will be created for the same key. Each idempotent request refreshes the cache for an additional 24 hours.

:::: tabs

::: tab Prefect library
```python
client.create_flow_run(
    flow_id="<flow-id>", 
    idempotency_key="do-not-create-two-runs"
)
```
:::

::: tab GraphQL API
```graphql
mutation {
  create_flow_run(input: { flow_id: "<flow-id>", idempotency_key: "any-key" }) {
    id
  }
}
```
:::

::::


### Flow groups vs flows

For flows which update regularly, you can provide a `flow_group_id` instead of a `flow_id`. If provided, the unique unarchived flow within the flow group will be scheduled for execution.
