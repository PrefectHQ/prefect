# Conclusion and Next Steps

In this tutorial we covered:

- Creating a project
- Registering and running flows
- Providing flow parameters at runtime
- Altering a flow's execution environment through it's
  [run-config](/orchestration/flow_config/run_configs.md)
- Enabling parallelism by swapping out a flow's
  [executor](/orchestration/flow_config/executors.md).

This is just the beginning; the Prefect API has many more features to explore!

## Examples

Prefect provides a number of [examples](/core/examples/overview.md) that illustrate
different aspects of developing and running flows. These examples can all be run
locally or through Prefect Cloud/Server. To create a new project and register all
examples, run the following:

You can register all the examples in a new project by running the following:

```
# Create a new "Prefect Examples" project
$ prefect create project "Prefect Examples"

# Register all the examples into the "Prefect Examples" project
$ prefect register --json https://docs.prefect.io/examples.json --project "Prefect Examples"
```

See the [examples](/core/examples/overview.md) page for more information.

## Concepts

Visit the [Concept](/orchestration/concepts/api.html) docs for actions such as
working directly with Prefect's [GraphQL
API](/orchestration/concepts/graphql.html), diving into the
[CLI](/orchestration/concepts/cli.html), setting [concurrency
limits](/orchestration/concepts/task-concurrency-limiting.html) on your Cloud runs,
and more.

## Agents

To learn more about Prefect agents, [flow
affinity](/orchestration/agents/overview.html#labels) via labels, or find
information on platform specific agents visit the
[agent](/orchestration/agents/overview.html) documentation.

## Flow Configuration

For information on all the options for configuring a flow for deployment, see
the [Flow Configuration](/orchestration/flow_config/overview.html) documentation.

## Deployment Recipes

Check out some of the [deployment
recipes](/orchestration/recipes/configuring_storage.html) that are written
for some example flow deployment patterns.
