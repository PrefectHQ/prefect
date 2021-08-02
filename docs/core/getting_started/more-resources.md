
# More Resources

The Core Quick Start guide has covered: 
- Installing prefect
- Running a flow

This is just the beginning; Prefect has many more resources and concepts to explore. 

## Orchestration

If you want greater orchestration for your flows, check out our [orchestration docs](/orchestration/README.md) about how to add an API and UI layer for your flows. 

## Video Guides

Check out the Prefect YouTube channel for advice and guides such as [how to get started with Prefect](https://youtu.be/iP7gR3r9DME) or [how to contribute to Prefect](https://youtu.be/qePaNCdySes). 

## The Prefect Blog

The [Prefect blog](https://www.prefect.io/resources) has lots of ideas and guides on simple ways to get started with Prefect. For new users on Core 0.15.0, our [New Flow Run Experience](https://www.prefect.io/blog/prefect-0-15-0-a-new-flow-run-experience) blog post sets out a new way to run flows with Prefect. 

## Examples

Prefect provides a number of [examples](/core/examples/overview.md) that illustrate
different aspects of developing and running flows. These examples can all be run
locally or through Prefect Cloud/Server. To create a new project and register all
examples, run the following:

```
# Create a new "Prefect Examples" project
$ prefect create project "Prefect Examples"

# Register all the examples into the "Prefect Examples" project
$ prefect register --json https://docs.prefect.io/examples.json --project "Prefect Examples"
```

See the [examples](/core/examples/overview.md) page for more information.

## Concepts

Visit the [Core Concepts](/core/concepts/tasks.html) docs for more information on tasks, flows and parameters and states. You can also see how to set up [notifications](/core/concepts/notifications.html#state-handlers) and find out how Prefect [caches and persists data](/core/concepts/persistence.html).


