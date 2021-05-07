# Task runs

::: tip Results
Prefect does not store the _results_ of your task runs. The data that your task returns is stored safely on your own infrastructure unless explicitly sent to Prefect's backend. 
:::

For monitoring task runs from the UI, see the [UI documentation on task runs](/orchestration/ui/task-runs.md).

## Prefect library

::: tip 
You should typically access task runs from a `FlowRunView` object. This will cache `TaskRunView` objects for finished tasks and pass the `flow_run_id` for you. Read the [flow run inspection documentation](./inspection#prefect-library) to get started.
:::

## GraphQL

### Querying for a single task run

### Querying for task run aggregates

## CLI

The CLI does not currently support looking up task run information. Would this be useful to you? Chime in [on GitHub](https://github.com/PrefectHQ/prefect/issues/4493).