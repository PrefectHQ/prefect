# FAQ

## Why did Prefect create and release Orion?

Orion represents three major objectives:
- embracing dynamic, DAG-free workflows
- an extraordinary developer experience
- transparent and observable orchestration rules

As Prefect has matured, so has the modern data stack. The on-demand, dynamic, highly scalable workflows that used to exist principally in the domain of data science and analytics are now prevalent throughout all of data engineering. Few companies have workflows that don’t deal with streaming data, uncertain timing, runtime logic, complex dependencies, versioning, or custom scheduling. 

This means that the current generation of workflow managers are built around the wrong abstraction: the DAG. DAGs are an increasingly arcane, constrained way of representing the dynamic, heterogeneous range of modern data and computation patterns. 

Furthermore, as workflows have become more complex, it has become even more important to focus on the developer experience of building, testing, and monitoring them.

And finally, this additional complexity means that providing clear and consistent insight into the behavior of the orchestration engine and any decisions it makes is critically important. 

Orion represents a unified solution to these three problems. It is capable of governing **any** code through a well-defined series of state transitions designed to maximize the user's understanding of what happened during execution. It's popular to describe "workflows as code" or "orchestration as code", but Orion represents "code as code": rather than ask users to change how they work to meet the requirements of the orchestrator, we've defined an orchestrator that adapts to how our users work. To achieve this, we've leveraged the familiar tools of native Python: first class functions, type annotations, and `async` support. Users are free to implement as much - or as little - of the Orion engine as is useful for their objectives. 
## Why is Orion being released as a technical preview?
Orion is the latest step in a long-term mission to codify the best practices of modern data engineering. Historically, Prefect has benefitted from looping our community in early to our product development lifecycle. We are continuing this tradition with Orion. The current codebase is the core of our new workflow engine. It meets our initial design objectives and we are excited to learn from our users' experiences in the wild. However, while it is fully functional, it is far from a finished product. Many conveniences and even some major features have not yet been implemented. Over the next few months, you can follow our development in the open -- and even participate yourself -- as we bring this product toward release. Until then, we will maintain the "technical preview" label to communicate the status of the project as not yet battle-tested in production. For production use cases, we currently recommend [Prefect Core](https://github.com/prefecthq/prefect).




## What is the roadmap for Orion?

One of the reasons we are open-sourcing the technical preview is to begin soliciting priorities from our community. We will integrate these with our internal designs to publish a clear roadmap for the project. For a preview of our current design objectives, please visit the [Orion overview page](https://prefect.io/orion).

## When will Orion be released?

Orion will remain in technical preview status until at least the end of 2021, and we expect to ship a stable release in early 2022. 
## How does Orion work?

The Orion technical preview consists of a few complementary parts:
- Python Client: where workflows are defined and executed
- Orion API: a REST API that exposes the central orchestration engine
- Metadata DB: a persistent store for states, results, and run metadata
- Dashboard: a UI for monitoring and interacting with the system

Most users will begin in the *client* by annotating a function as either a `flow` or `task`. Every time that function is called, it collaborates with the *orchestration engine* via the Orion API. The orchestration engine is responsible for governing the function's transitions through various [states](concepts/states.md) that represent its progress. The orchestration engine is composed of a variety of rules that enforce helpful behaviors. For example, one rule might intercept tasks that fail and instruct them to retry; another might identify that a task was cached and instruct it not to run at all. All states and metadata are stored in the *metadata database*. The Dashboard leverages all of this to deliver an interactive way to browse live and historical data.

!!! tip "Always On"
    Orion doesn't have to be run as a persistent service. Even interactive executions will persist metadata in your locally-configured database. This means that you can run scripts interactively and spin up the Dashboard after-the-fact, but still see all of your historical interactive runs.
