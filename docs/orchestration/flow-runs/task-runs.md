# Inspecting task runs

::: tip Results
Prefect does not store the _results_ of your task runs. The data that your task returns is stored safely on your own infrastructure unless explicitly sent to Prefect's backend. 
:::

For monitoring task runs from the UI, see the [UI documentation on task runs](/orchestration/ui/task-runs.md).

## Prefect library

::: tip 
You should typically access task runs from a `FlowRunView` object. This will cache `TaskRunView` objects for finished tasks and pass the `flow_run_id` for you. Read the [flow run inspection documentation](./inspection#prefect-library) to get started.
:::

## GraphQL

### Querying for task runs in a flow run

Here we query for all of the task runs in a run of the `prefect.hello_world` flow

```graphql
query {
  task_run(where: {flow_run_id: {_eq: "8e445d74-9ca6-425b-98e5-72754b7ea174"}}) {
    id
    state
    start_time
    task {
      slug
    }
  }
}
```

Example response

```json
{
  "data": {
    "task_run": [
      {
        "id": "c8751f34-9d5e-4ea7-aead-8b50978dabb7",
        "state": "Success",
        "start_time": "2021-05-12T18:00:01.696849+00:00",
        "task": {
          "slug": "say_hello-1"
        }
      },
      {
        "id": "f5f422f6-4f56-45d2-bd55-5ea048070d84",
        "state": "Success",
        "start_time": "2021-05-12T18:00:00.229202+00:00",
        "task": {
          "slug": "capitalize-1"
        }
      },
      {
        "id": "7cc167d3-737d-4187-85d8-d5e5a75fbd93",
        "state": "Success",
        "start_time": "2021-05-12T17:59:58.33804+00:00",
        "task": {
          "slug": "name"
        }
      }
    ]
  }
}
```

### Querying for task run aggregates

```graphql
query {
  task_run_aggregate(where: {state: {_eq: "Success"}}) {
    aggregate{
      count
    }
  }
}
```

Example response

```json
{
  "data": {
    "task_run_aggregate": {
      "aggregate": {
        "count": 258
      }
    }
  }
}
```

## CLI

The CLI does not currently support looking up task run information. Would this be useful to you? Chime in [on GitHub](https://github.com/PrefectHQ/prefect/issues/4493).
