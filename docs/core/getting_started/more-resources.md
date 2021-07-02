
# More Resources

The Core Quick Start guide has covered: 
- Installing prefect
- Running a flow

This is just the beginning; Prefect has many more resources and concepts to explore. 

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

Visit the [Core Concepts](/core/concepts/api.html) docs for more information on tasks, flows and parameters and states. You can also see how to set up [notifications](/core/concepts/notifications.html#state-handlers) and find out how Prefect [caches and persists data](/core/concepts/persistence.html).

## Video Guides

Check out the Prefect YouTube channel for advice and guides such as [how to get started with Prefect](https://youtu.be/iP7gR3r9DME) or [how to contribute to Prefect](https://youtu.be/qePaNCdySes). 

## The Prefect Blog

The [Prefect blog](https://www.prefect.io/resources) has lots of extra information and updates about Prefect and ideas on simple ways to get started: 

Learn about the [new flow run experience](https://www.prefect.io/blog/prefect-0-15-0-a-new-flow-run-experience)

Learn how to get started with parallel computation: [Part 1](https://medium.com/the-prefect-blog/getting-started-with-parallel-computation-60da4850f0)[Part 2](https://medium.com/the-prefect-blog/prefect-getting-started-with-operationalizing-your-python-code-999a0bf1dda8)

[Using Great Expectations with Prefect](https://medium.com/hashmapinc/understanding-great-expectations-and-how-to-use-it-7754c78962f4)

[Possible First Project](https://medium.com/the-prefect-blog/my-prefect-home-c05ebe625410)

[Using Notifiers](https://medium.com/the-prefect-blog/something-went-wrong-b3bd5899a1ef)