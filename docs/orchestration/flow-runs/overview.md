---
sidebarDepth: 0
editLink: false
---

# Overview

When a flow is run with Prefect Core, it executes locally and its state is not persisted. When a flow is run with a Prefect backend i.e. Prefect Cloud, information about the flow's execution is streamed to the backend for live inspection of your flow's status. This information is persisted for later access. In the Prefect backend, a flow run represents the full picture of your flow's execution from scheduling to completion.

## Creating flow runs

Flow runs can be created with
- [the Prefect CLI](./creation.md#cli)
- [the UI](/ui/dashboard.md)
- [the Python client](./creation.md#prefect-library)
- [a task in another Flow](./creation.md#task)
- [a schedule](./scheduling.md)
- [a GraphQL API call](./creation.md#graphql)

By creating a flow run you are indicating that you'd like your flow to be executed. Your flow runs will move through a series of states:
- **Scheduled**: Your flow run is created and scheduled to run at some point
- **Submitted**: An agent has picked up your flow run and submitted it for execution in the relevant infrastructure
- **Running**: The tasks of your flow run are executing
- **Finished**: Either `Success` or `Failure` depending on the outcome of the run

For more details on states, see the [states documentation](/core/concepts/states.md).

For more details on how to create a flow run, see the [flow run creation documentation](./creation.md).

Or... keep reading for an overview of how to inspect flow runs.

## Inspecting flow runs

Flow run information is sent to Prefect's backend during the run and persists there after the run completes. The Prefect GraphQL API allows you to craft queries that retrieve exactly the information you need about any flow run. We also provide tooling in the Prefect Core library to simplify common access patterns.

- For programatic inspection of flow runs, see the [Python flow run documentation](./inspection#prefect-library).
- For customized GraphQL queries for flow run data, see [the documentation on query for flow runs](./inspection#graphql).
- For monitoring flow runs from the UI, see the [UI documentation on flow runs](../ui/flow-run.md).

Or... keep reading for an overview of the task run concept.

## Inspecting task runs

Each flow contains tasks which actually do the _work_ of your flow. The state of your tasks is also tracked in Prefect's backend for inspection.

Similarly to flow runs, task runs can be inspected with various methods

- For programatic inspection of task runs, see the [Python task run documentation](./task-runs.md#prefect-libary).
- For passing data from one flow to another flow, see the [`get_task_run_result` task documentation](./task-runs.md#task).
- For customized GraphQL queries for task run data, see [the documentation on query for task runs](./task-runs.md#graphql).
- For monitoring task runs from the UI, see the [UI documentation on task runs](../ui/task-run.md).

For more details on task runs, see the [task run documentation](./task-runs.md).

Or... keep reading for an overview of how to limit the number of concurrent runs.

## Limiting concurrency <Badge text="Cloud"/>

By default, there is no limit to the number of concurrent flow runs or task runs you can have. Prefect supports _unlimited_ concurrent execution of your flows. However, there are some cases where _you_ want to enforce some limits to reduce strain on your infrastructure. 

The number of concurrent flow runs can be limited by label. See the [flow run concurrency documentation](./concurrency-limits.md#flow-run-limits).

The number of concurrent task runs can be limited by tag. See the [task run concurrency documentation](./concurrency-limits.md#task-run-limits).

## Next steps
<!-- How does this section relate to other docs? -->

Hopefully you have an understanding of how to create and interact with your flow runs now. Take a look at some related docs next:

- Flows and their runs are deeply configurable, check out the [flow configuration documentation](../flow_config/overview.md#overview)
- An agent is necessary to submit the flow runs you create for execution, check out the [agent documentation](../agents/overview.md#overview)