# Frequently Asked Questions

## Orion

### Why "Orion"?

As an advanced orchestration engine, Orion practically named itself: **OR**chestrat**ION**.

The word "Prefect" stems from the Latin "praefectus," meaning "one who is in charge." A prefect is an official who oversees a domain and ensures that rules are followed. Similarly, Prefect software ensures that workflows are orchestrated properly.

Curiously enough, Orion is also the home of Ford Prefect, a roving researcher for that wholly remarkable book, _The Hitchhiker's Guide to the Galaxy_.

### Why was Orion created?

Orion has three major objectives:

- embracing dynamic, DAG-free workflows
- an extraordinary developer experience
- transparent and observable orchestration rules

As Prefect has matured, so has the modern data stack. The on-demand, dynamic, highly scalable workflows that used to exist principally in the domain of data science and analytics are now prevalent throughout all of data engineering. Few companies have workflows that don’t deal with streaming data, uncertain timing, runtime logic, complex dependencies, versioning, or custom scheduling.

This means that the current generation of workflow managers are built around the wrong abstraction: the DAG. DAGs are an increasingly arcane, constrained way of representing the dynamic, heterogeneous range of modern data and computation patterns.

Furthermore, as workflows have become more complex, it has become even more important to focus on the developer experience of building, testing, and monitoring them.

And finally, this additional complexity means that providing clear and consistent insight into the behavior of the orchestration engine and any decisions it makes is critically important.

_Orion represents a unified solution to these three problems_. It is capable of governing **any** code through a well-defined series of state transitions designed to maximize the user's understanding of what happened during execution. It's popular to describe "workflows as code" or "orchestration as code", but Orion represents "code as code": rather than ask users to change how they work to meet the requirements of the orchestrator, we've defined an orchestrator that adapts to how our users work. To achieve this, we've leveraged the familiar tools of native Python: first class functions, type annotations, and `async` support. Users are free to implement as much - or as little - of the Orion engine as is useful for their objectives.

### Why is Orion a "technical preview"?

Orion is the latest step in a long-term mission to codify the best practices of modern data engineering. Historically, Prefect has benefitted from looping our community in early to our product development lifecycle. We are continuing this tradition with Orion. The current codebase is the core of our new workflow engine. It meets our initial design objectives and we are excited to learn from our users' experiences in the wild. However, while it is fully functional, it is far from a finished product. Many conveniences and even some major features have not yet been implemented. Over the next few months, you can follow our development in the open -- and even participate yourself -- as we bring this product toward release. Until then, we will maintain the "technical preview" label to communicate the status of the project as not yet battle-tested in production. For production use cases, we currently recommend [Prefect Core](https://github.com/prefecthq/prefect).

### Can I use Orion in production?

Orion is alpha software and we do not recommend Orion for production use at this time. 

## Features

### What's on the Orion roadmap?

We will publish a complete roadmap for Orion soon. Here are a few important milestones currently under consideration:

- Python client
    - Task mapping
    - Porting the Prefect task library and integrations
    - Track inputs across tasks
- UI
    - Task Run pages
    - Create deployments from UI
    - Create schedules from UI
    - Share dashboards
    - Configure storage locations
    - Update server settings from UI
    - View flow run execution and data tracking in schematic
- Orion server
    - States
        - Add `CRASHED` states for capturing and reacting to infrastructure failures
    - Orion engine orchestration rules
        - Configurable retry on `CRASHED`
        - Automatically expire caches when tasks are taken out of `TERMINAL` states
        - Linear scheduling: cancel runs attempting to enter `RUNNING` states if another run of the same flow is already running
        - Exponential backoff for `AWAITING_RETRY`
    - Configurable storage locations for flows and persisted data
- Prefect IDE
    - Time travel debugging: download states from remote runs to replay them interactively


One of the reasons we are open-sourcing the technical preview is to begin soliciting priorities from our community. We will integrate these with our internal designs to publish a clear roadmap for the project.

### Does Orion support mapping?

Mapping is one of the most popular features in Prefect Core, allowing users to tap into their executor's native fan-out abilities. An equivalent `.map()` operator will be released for Orion soon. For now, users can take advantage of Orion's support for native Python to call tasks in loops:

```python
@flow
def my_flow():

    # map over a constant
    for i in range(10):
        my_mapped_task(i)

    # map over a task's output
    l = list_task()
    for i in l.wait().result():
        my_mapped_task_2(i)
```

Note that when tasks are called on constant values, they can not detect their upstream edges automatically. In this example, `my_mapped_task_2` does not know that it is downstream from `list_task()`. Orion will have convenience functions for detecting these associations, and Orion's `.map()` operator will automatically track them.

### How do I tell enforce ordering between tasks that don't share data?

To create a dependency between two tasks that do not exchange data but one needs to wait for the other to finish, use the special [`wait_for` keyword argument][prefect.tasks.task.__call__]:

```python
@task
def task_1():
    pass

@task
def task_2():
    pass

@flow
def my_flow():
    x = task_1()

    # task 2 will wait for task_1 to complete
    y = task_2(wait_for=[x])
```

### When will Orion be released?

Orion will remain in technical preview status until at least the end of 2021, and we expect to ship a stable release in early 2022.

## Deployment

### How is Orion organized?

The Orion technical preview consists of a few complementary parts:

- Python Client: where workflows are defined and executed
- Orion API: a REST API that exposes the central orchestration engine
- Metadata DB: a persistent store for states, results, and run metadata
- Dashboard: a UI for monitoring and interacting with the system

Most users will begin in the *client* by annotating a function as either a `flow` or `task`. Every time that function is called, it collaborates with the *orchestration engine* via the Orion API. The orchestration engine is responsible for governing the function's transitions through various [states](concepts/states) that represent its progress. The orchestration engine is composed of a variety of rules that enforce helpful behaviors. For example, one rule might intercept tasks that fail and instruct them to retry; another might identify that a task was cached and instruct it not to run at all. All states and metadata are stored in the *metadata database*. The Dashboard leverages all of this to deliver an interactive way to browse live and historical data.

!!! tip "Always On"
Thanks to ephemeral APIs, Orion doesn't have to be run as a persistent service. Running a flow interactively will still properly interact with the orchestration API and persist metadata in your locally-configured database. You only need to run a stateful Orion server and related services when you require the features they provide, such as automatic scheduling and execution, or a hosted UI. This means that for interactive runs against a SQLite database, Orion can operate as a completely serverless platform.

### What databases does Orion support?

Orion works with SQLite and Postgres. New Orion installs default to a SQLite database hosted at `~/.prefect/orion.db`.

### How do I choose between SQLite and Postgres?

SQLite is appropriate for getting started and exploring Orion. We have tested it with up to hundreds of thousands of task runs. Many users may be able to stay on SQLite for some time. However, under write-heavy workloads, SQLite performance can begin to suffer. Users running many flows with high degrees of parallelism or concurrency may prefer to start with Postgres.

This answer will be updated with more concrete guidelines in the future.

## Relationship with Prefect Core

### Does Orion replace Prefect Core?

Orion represents the future of Prefect's orchestration engine and API. It will power a new generation of self-hosted and commercial Prefect products. We are releasing it as a technical preview because it has achieved its primary design objectives, but it still has a ways to go. In the coming months, you will see Orion undergo rapid changes as it approaches a stable release in early 2022. At that time, Orion will become the "default" version of Prefect, replacing Prefect Core and powering all of our products.

### Can I still use Prefect Core?

Yes! Prefect Core is our battle-tested, production-ready workflow engine. Its API has remained stable - and almost completely backwards compatible - for almost two years. Our Prefect Cloud customers have used it to execute nearly half a billion tasks this year, and our open-source users have stressed it even further. For these reasons, as a reflection of its maturity, Prefect Core will be promoted to 1.0 in the near future. Prefect 1.0 will remain fully supported by the Prefect team for at least one year after Orion's release.

### Is there an upgrade guide from Prefect Core to Prefect Orion?

As Orion moves closer to release, we will provide upgrade guides and tools to make Orion adoption as easy as possible for Prefect 1.0 users.
