# Creating flow runs

Creating a flow run indicates to the backend that you'd like your flow to be executed. The backend will then place your flow run into a queue that agents poll. When your flow run is ready to execute, the agent will deploy the flow run to its infrastructure and the flow run will report its status to the backend.

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

!!! tip Local flow runs
    `prefect run` can be used to execute a local flow as well if you provide a `--path` or a `--module` to load the flow from
:::


!!! tip Agentless flow run execution

    `prefect run` can be used to create and execute a flow run in the current environment, without requiring an agent. Just provide the `--execute` flag. This allows you to take ownership of your flow's execution environment or run flows locally while retaining the benefits of the backend API. There are a few different behaviors from typical flow runs:

    - Other than environment variables, your `RunConfig` will be ignored; by using this, you are taking ownership of your flow's environment.
    - The flow run will be given a special label to indicate that it should not be picked up by an agent.
    - If the process executing the flow run fails, the flow run will be marked as failed.
    - If the flow run has a task with a long retry, the process will sleep. With agents, it would exit fully and be re-deployed when ready.
    - `breakpoint()` can be used in tasks to enter a debugging session with local executors

:::

## Python client

Flow runs can be created using the Prefect `Client` interface in the `prefect` core Python library:

```python
from prefect import Client

client = Client()
client.create_flow_run(flow_id="d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7")
```

See [optional settings](#optional-settings) for additional information that can be passed.


## Task

Flow runs can be created from within another flow run using the `create_flow_run` task in the Prefect task library:

```python
from prefect import Flow
from prefect.tasks.prefect import create_flow_run, wait_for_flow_run

with Flow("parent-flow") as flow:
  # Create the child flow run, look up the flow by name
  child_run_id = create_flow_run(flow_name="hello-world")

  # Wait for the flow run to complete before considering this flow run done
  # This is optional, this flow could exit and leave the other one running
  wait_for_flow_run(child_run_id)
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

CLI:
```bash
$ prefect run --id "d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7" --param a=2
$ prefect run --path flow.py --param "a param with space"=2
```

Python client:
```python
client.create_flow_run(
    flow_id="d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7", 
    parameters={"a": 2}
)
```

GraphQL API:
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


### Flow run names

By default, a flow run is given an automatically generated name. However, a custom run name can be passed.

CLI:
```bash
$ prefect run --id "d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7" --run-name "docs example hello-world"
```

Python client:
```python
client.create_flow_run(
    flow_id="d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7", 
    flow_run_name="docs example hello-world"
)
```

GraphQL API:
```graphql
mutation {
  create_flow_run(input: { 
  flow_id: "d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7", 
  flow_run_name: "docs example hello-world",
}
```


### Start times

Flows can be assigned a start time in the future rather than being marked for execution immediately.

Python client:
```python
client.create_flow_run(
    flow_id="d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7", 
    scheduled_start_time=pendulum.now().add(minutes=10)
)
```

GraphQL API:
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


!!! tip Generating time strings for GraphQL
    GraphQL expects ISO formatted datetime strings. This is default when you cast a `pendulum.DateTime` to a string. You can also explicitly call the conversion `pendulum.now().isoformat()` in newer versions of `pendulum`.
:::

### Idempotency

If you provide an `idempotency_key` when creating a flow run, you can safely attempt to recreate that run again without actually recreating it. This is helpful when you have a substandard network connection or when you're worried about redundancy in your run triggers. Note that idempotency keys do not expire. To create a new run, a new idempotency key must be provided. 

Python client:
```python
client.create_flow_run(
    flow_id="d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7", 
    idempotency_key="do-not-create-two-runs"
)
```

GraphQL API:
```graphql
mutation {
  create_flow_run(input: { flow_id: "d7bfb996-b8fe-4055-8d43-2c9f82a1e3c7", idempotency_key: "any-key" }) {
    id
  }
}
```



### Flow groups vs flows

For flows which update regularly, you can provide a `flow_group_id` instead of a `flow_id`. If provided, the unique unarchived flow within the flow group will be scheduled for execution.
