---
description: Answers to frequently asked questions about Prefect 2.
tags:
    - FAQ
    - frequently asked questions
    - questions
    - license
    - databases
---

# Frequently Asked Questions

## Prefect 2

### How is Prefect 2 licensed?

Prefect 2 is licensed under the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0), an [OSI approved](https://opensource.org/licenses/Apache-2.0) open-source license. If you have any questions about licensing, please [contact us](mailto:hello@prefect.io).

## The Orion Engine

### Why "Orion"?

As an advanced orchestration engine, Orion practically named itself: **OR**chestrat**ION**.

The word "Prefect" stems from the Latin "praefectus," meaning "one who is in charge." A prefect is an official who oversees a domain and ensures that rules are followed. Similarly, Prefect software ensures that workflows are orchestrated properly.

Curiously enough, Orion is also the home of Ford Prefect, a roving researcher for that wholly remarkable book, _The Hitchhiker's Guide to the Galaxy_.

### Why was Orion created?

Orion has three major objectives:

- Embracing dynamic, DAG-free workflows
- An extraordinary developer experience
- Transparent and observable orchestration rules

As Prefect has matured, so has the modern data stack. The on-demand, dynamic, highly scalable workflows that used to exist principally in the domain of data science and analytics are now prevalent throughout all of data engineering. Few companies have workflows that don’t deal with streaming data, uncertain timing, runtime logic, complex dependencies, versioning, or custom scheduling.

This means that the current generation of workflow managers are built around the wrong abstraction: the directed acyclic graph (DAG). DAGs are an increasingly arcane, constrained way of representing the dynamic, heterogeneous range of modern data and computation patterns.

Furthermore, as workflows have become more complex, it has become even more important to focus on the developer experience of building, testing, and monitoring them. Faced with an explosion of available tools, it is more important than ever for development teams to seek orchestration tools that will be compatible with any code, tools, or services they may require in the future.

And finally, this additional complexity means that providing clear and consistent insight into the behavior of the orchestration engine and any decisions it makes is critically important.

_Orion represents a unified solution to these three problems_.

Orion is capable of governing **any** code through a well-defined series of state transitions designed to maximize the user's understanding of what happened during execution. It's popular to describe "workflows as code" or "orchestration as code," but Orion represents "code as workflows": rather than ask users to change how they work to meet the requirements of the orchestrator, we've defined an orchestrator that adapts to how our users work.

To achieve this, we've leveraged the familiar tools of native Python: first class functions, type annotations, and `async` support. Users are free to implement as much &mdash; or as little &mdash; of the Orion engine as is useful for their objectives.

### If I’m using Prefect Cloud 2, do I still need to run Orion locally?

No, Prefect Cloud 2 hosts an instance of Orion for you. In fact, each workspace in Prefect Could 2 corresponds directly to a single instance of Prefect Orion. See [Getting Started with Prefect Cloud](/ui/cloud-getting-started/) for more information.


## Features

### Does Prefect 2 support mapping?

Yes! For more information, see the [`Task.map` API reference](/api-ref/prefect/tasks/#prefect.tasks.Task.map)

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

Note that when tasks are called on constant values, they cannot detect their upstream edges automatically. In this example, `my_mapped_task_2` does not know that it is downstream from `list_task()`. Prefect will have convenience functions for detecting these associations, and Prefect's `.map()` operator will automatically track them.

### How do I enforce ordering between tasks that don't share data?

To create a dependency between two tasks that do not exchange data, but one needs to wait for the other to finish, use the special [`wait_for`][prefect.tasks.Task.__call__] keyword argument:

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

### Does Prefect support proxies?

Yes!

Prefect supports communicating via proxies through the use of environment variables. You can read more about this in the [Installation](/getting-started/installation/#proxies) documentation and the article [Using Prefect Cloud with proxies](https://discourse.prefect.io/t/using-prefect-cloud-with-proxies/1696).

### Can I run Prefect flows on Linux?

Yes! 

See the [Installation](/getting-started/installation/) documentation and [Linux installation notes](/getting-started/installation/#linux-installation-notes) for details on getting started with Prefect on Linux.

### Can I run Prefect flows on Windows?

Yes!

See the [Installation](/getting-started/installation/) documentation and [Windows installation notes](/getting-started/installation/#windows-installation-notes) for details on getting started with Prefect on Windows.

### What external requirements does Prefect have?

Prefect does not have any additional requirements besides those installed by `pip install --pre prefect`. The entire system, including the UI and services, can be run in a single process via `prefect orion start` and does not require Docker.

To use PostgreSQL, users must provide the [connection string][prefect.settings.PREFECT_ORION_DATABASE_CONNECTION_URL] for a running database via the `PREFECT_ORION_DATABASE_CONNECTION_URL` environment variable.

### What databases does Prefect support?

Prefect works with SQLite and PostgreSQL. New Prefect installs default to a SQLite database hosted at `~/.prefect/orion.db`.

### How do I choose between SQLite and Postgres?

SQLite is appropriate for getting started and exploring Prefect. We have tested it with up to hundreds of thousands of task runs. Many users may be able to stay on SQLite for some time. However, under write-heavy workloads, SQLite performance can begin to suffer. Users running many flows with high degrees of parallelism or concurrency may prefer to start with PostgreSQL.

This answer will be updated with more concrete guidelines in the future.

## Relationship with other Prefect products

### Can a flow written with Prefect 1 be orchestrated with Prefect 2 and vice versa?

No. Flows written with the Prefect 1 client must be rewritten with the Prefect 2 client. For most flows, this should take just a few minutes. See our [migration guide](/migration-guide/) and our [Upgrade to Prefect 2](https://www.prefect.io/guide/blog/upgrade-to-prefect-2/) post for more information.
