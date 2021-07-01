
# More Resources

The Core Quick Start guide has covered: 
- Installing prefect
- Writing a flow

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

Visit the [Concept](/orchestration/concepts/api.html) docs for actions such as
working directly with Prefect's [GraphQL
API](/orchestration/concepts/graphql.html), diving into the
[CLI](/orchestration/concepts/cli.html), setting [concurrency
limits](/orchestration/concepts/task-concurrency-limiting.html) on your Cloud runs,
and more.


## Video Guides

Check out the Prefect YouTube channel for advice and guides such as [how to Deploy Prefect Server.](https://youtu.be/yjORjWHyKhg)

## Ideas and Tutorials from the Prefect Blog
The Prefect blog has lots of guides on getting started and ideas on simple ways to get started with Prefect

Learn how to get started with parallel computation: [Part 1](https://medium.com/the-prefect-blog/getting-started-with-parallel-computation-60da4850f0)[Part 2](https://medium.com/the-prefect-blog/prefect-getting-started-with-operationalizing-your-python-code-999a0bf1dda8)

[Get started with Prefect Cloud on AWS](https://medium.com/the-prefect-blog/seamless-move-from-local-to-aws-kubernetes-cluster-with-prefect-f263a4573c56)

[Set up Server on GCP](https://medium.com/the-prefect-blog/prefect-server-101-deploying-to-google-cloud-platform-47354b16afe2)

[Possible First Project](https://medium.com/the-prefect-blog/my-prefect-home-c05ebe625410)

[Using Notifiers](https://medium.com/the-prefect-blog/something-went-wrong-b3bd5899a1ef)