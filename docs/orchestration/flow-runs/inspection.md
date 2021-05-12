# Inspecting flow runs

<!-- TODO -->

For monitoring flow runs from the UI, see the [UI documentation on flow runs](../ui/flow-run.md).

## CLI

## Prefect library

The Prefect library provides an object for inspecting flow runs without writing queries at `prefect.backend.FlowRunView`.

### Creating a `FlowRunView`

A `FlowRunView` can be created using the `from_flow_run_id` class method. This methods will query for flow run information and populate a `FlowRunView` instance.

```python
from prefect.backend import FlowRunView

flow_run = FlowRunView.from_flow_run_id("4c0101af-c6bb-4b96-8661-63a5bbfb5596")
```

:::warning Immutability
:::

### Getting flow run states

The state of the flow run is inspectable using the `.state` property
```python
flow_run.state
::: tip Watching a flow run
:::

### Getting flow run logs

### Getting flow metadata

::: tip Flow metadata caching
:::

### Getting flow task runs

::: tip Task run caching
:::

For more details on the `TaskRunView`, see [the task runs documentation](./task-runs.md).

## GraphQL

### Querying for a single flow run

### Querying for flow run aggregates