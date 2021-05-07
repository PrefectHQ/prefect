# Overview

When a flow is run with Prefect Core, it runs locally and its state is not persisted. When a flow is run with a backend like Prefect Cloud, information about the flow state is streamed to the backend for live inspection of your flow's status. This information is persisted for later access. In the Prefect backend, a flow run represents the full picture of your flow's execution from scheduling to completion.

## Creating flow runs

Flow runs can be created:

- [with the Prefect CLI](./creation.md#cli)
- [with the UI](/ui/flow_run.md#create)
- [with the Prefect Client](./creation.md#client)
- [on a schedule](./scheduling.md)
- [with a GraphQL API call](./creation.md#graphql)

By creating a flow run you are indicating that you'd like your flow to be executed. Your flow runs will move through a series of states:

- Scheduled: Your flow run is created and scheduled to run sometime. When the start time is reached, it is placed in a pollable "ready" queue
- Submitted: An agent has picked up your flow run and submitted it for execution in the relevant infrastructure
- Running: The tasks of your flow run are executing
- Finished: Either `Success` or `Failure` depending on the outcome of the run

For more details on states, see the [states documentation](/core/concepts/states.md).

For more details on how to create a flow run, see the [flow run creation documentation](./creation.md).

Or... keep reading for an overview of how to inspect flow runs.

## Inspecting flow runs

Flow run information is sent to Prefect's backend during the run and persists there after the run completes. The Prefect GraphQL API allows you to craft queries that retrieve exactly the information you need about any flow run. We also provide tooling in the Prefect Core library to simplify common access patterns.

For command-line inspection of flow runs, see the [flow run CLI documentation](./inspection#cli).

For programatic inspection of flow runs, see the [Prefect library flow run documentation](./inspection#prefect-library).

For customized GraphQL queries for flow run data, see [the documentation on query for flow runs](./inspection#graphql).

Or... keep reading for an overview of the task run concept.

## Task runs

Each flow contains tasks which actually _do the work_ of your flow. The state of your tasks is also tracked in Prefect's backend for inspection.

::: tip
Prefect does not store the _results_ of your task runs. The data that your task returns is stored safely on your own infrastructure unless explicitly sent to Prefect's backend. 
:::

Similarly to flow runs, task runs can be ins

For more details on task runs, see the [task run documentation](./task-runs.md).

Or... keep reading for an overview of how to limit the number of concurrent runs.

## Limiting concurrency

By default, there is no limit to the number of concurrent flow runs or task runs you can have. Prefect supports _unlimited_ concurrent execution of your flows. However, there are some cases where _you_ want to enforce some limits to reduce strain on your infrastructure. 

The number of concurrent flow runs can be limited by label. See the [flow run concurrency documentation](./concurrency-limits.md#flow-run) for details.

The number of concurrent task runs can be limited by tag. See the [task run concurrency documentation](./concurrency-limits.md#task-run) for details.

## Next steps

Now that you understand how to create and interact with a flow run, you're ready to learn how to customize the execution of your flow. Flow runs are deeply configurable, check out the [flow run configuration documentation](/orchestration/flow_config/overview.md) next.