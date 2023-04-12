---
description: Answers to frequently asked questions about Prefect.
tags:
    - FAQ
    - frequently asked questions
    - questions
    - license
    - databases
---

# Frequently Asked Questions

## Prefect

### How is Prefect licensed?

Prefect is licensed under the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0), an [OSI approved](https://opensource.org/licenses/Apache-2.0) open-source license. If you have any questions about licensing, please [contact us](mailto:hello@prefect.io).

### Is the Prefect v2 Cloud URL different than the Prefect v1 Cloud URL?  

Yes. Prefect Cloud for v2 is at [app.prefect.cloud/](https://app.prefect.cloud) while Prefect Cloud for v1 is at [cloud.prefect.io](https://cloud.prefect.io/).

## The Prefect Orchestration Engine

### Why was the Prefect orchestration engine created?

The Prefect orchestration engine has three major objectives:

- Embracing dynamic, DAG-free workflows
- An extraordinary developer experience
- Transparent and observable orchestration rules

As Prefect has matured, so has the modern data stack. The on-demand, dynamic, highly scalable workflows that used to exist principally in the domain of data science and analytics are now prevalent throughout all of data engineering. Few companies have workflows that don’t deal with streaming data, uncertain timing, runtime logic, complex dependencies, versioning, or custom scheduling.

This means that the current generation of workflow managers are built around the wrong abstraction: the directed acyclic graph (DAG). DAGs are an increasingly arcane, constrained way of representing the dynamic, heterogeneous range of modern data and computation patterns.

Furthermore, as workflows have become more complex, it has become even more important to focus on the developer experience of building, testing, and monitoring them. Faced with an explosion of available tools, it is more important than ever for development teams to seek orchestration tools that will be compatible with any code, tools, or services they may require in the future.

And finally, this additional complexity means that providing clear and consistent insight into the behavior of the orchestration engine and any decisions it makes is critically important.

_The Prefect orchestration engine represents a unified solution to these three problems_.

The Prefect orchestration engine is capable of governing **any** code through a well-defined series of state transitions designed to maximize the user's understanding of what happened during execution. It's popular to describe "workflows as code" or "orchestration as code," but the Prefect engine represents "code as workflows": rather than ask users to change how they work to meet the requirements of the orchestrator, we've defined an orchestrator that adapts to how our users work.

To achieve this, we've leveraged the familiar tools of native Python: first class functions, type annotations, and `async` support. Users are free to implement as much &mdash; or as little &mdash; of the Prefect engine as is useful for their objectives.

### If I’m using Prefect Cloud 2, do I still need to run a Prefect server locally?

No, Prefect Cloud hosts an instance of the Prefect API for you. In fact, each workspace in Prefect Cloud corresponds directly to a single instance of the Prefect orchestration engine. See the [Prefect Cloud Overview](/ui/cloud/) for more information.


## Features

### Does Prefect support mapping?

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

### Can I enforce ordering between tasks that don't share data?

Yes! For more information, see the [`Tasks` section](/concepts/tasks/#wait-for).

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

Prefect does not have any additional requirements besides those installed by `pip install --pre prefect`. The entire system, including the UI and services, can be run in a single process via `prefect server start` and does not require Docker.

Prefect Cloud users do not need to worry about the Prefect database. Prefect Cloud uses PostgreSQL on GCP behind the scenes. To use PostgreSQL with a self-hosted Prefect server, users must provide the [connection string][prefect.settings.PREFECT_API_DATABASE_CONNECTION_URL] for a running database via the `PREFECT_API_DATABASE_CONNECTION_URL` environment variable.

### What databases does Prefect support?

A self-hosted Prefect server can work with SQLite and PostgreSQL. New Prefect installs default to a SQLite database hosted at `~/.prefect/prefect.db` on Mac or Linux machines. SQLite and PostgreSQL are not installed by Prefect.

### How do I choose between SQLite and Postgres?

SQLite generally works well for getting started and exploring Prefect. We have tested it with up to hundreds of thousands of task runs. Many users may be able to stay on SQLite for some time. However, for production uses, Prefect Cloud or self-hosted PostgreSQL is highly recommended. Under write-heavy workloads, SQLite performance can begin to suffer. Users running many flows with high degrees of parallelism or concurrency should use PostgreSQL.

## Relationship with other Prefect products

### Can a flow written with Prefect 1 be orchestrated with Prefect 2 and vice versa?

No. Flows written with the Prefect 1 client must be rewritten with the Prefect 2 client. For most flows, this should take just a few minutes. See our [migration guide](/migration-guide/) and our [Upgrade to Prefect 2](https://www.prefect.io/guide/blog/upgrade-to-prefect-2/) post for more information.

### Can a use Prefect 1 and Prefect 2 at the same time on my local machine?

Yes. Just use different virtual environments.
