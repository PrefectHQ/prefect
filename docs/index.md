---
description: Learn about Prefect 2.0, our second-generation workflow orchestration engine.
tags:
    - getting started
    - overview
---

![Prefect 2.0 logo](./img/logos/prefect-2-logo-dark.png)

#

## Welcome to Prefect!

Prefect is Air Traffic Control for your dataflows. It's the coordination plane that provides you with everything from dataflow observability to dataflow orchestration. 

## Why Prefect?

If you move data then you probably need the following functionality:

- [schedules](concepts/schedules/)
- [retries](concepts/tasks/#task-arguments)
- [logging](concepts/logs/)
- [caching](concepts/tasks/#caching)
- [notifications](ui/notifications/)
- [observability](/ui/overview/)

Coding all these features for your dataflows is a huge pain that takes a lot of time. 

That's why Prefect 2.0 offers all this functionality and more! 

All it takes to get started is a adding a few decorators and a little configuration. Check out this quick example. 

## Brief example

The code below fetches data about GitHub stars for two repositories. Add the three highlighted lines of code to your functions and you're off to the races! 


```python hl_lines="1 4 10"
from prefect import flow, task
import httpx

@task(retries=3)
def get_stars(repo):
    url = f"https://api.github.com/repos/{repo}"
    count = httpx.get(url).json()["stargazers_count"]
    print(f"{repo} has {count} stars!")

@flow
def github_stars(repos):
    for repo in repos:
        get_stars(repo)

# call the flow!
github_stars(["PrefectHQ/Prefect", "PrefectHQ/miter-design"])
```

By adding `retries=3 ` to the `task` decorator, the `get_stars` function will automatically rerun up to three times on failure!

### Observe in the Prefect Orion UI dashboard 
Fire up the UI locally to visualize the task run history and gain insight into their execution:

```bash
prefect orion start
```

![](./img/ui/orion-dashboard.png)

## Other Prefect data coordination benefits

### A user friendly GUI dashboard for your dataflows
In the [Prefect Orion UI](ui/overview/) shown above you can quickly set up notifications, visualize run history, and schedule your dataflows.  

### Graceful failures
Inevitably dataflows will fail. Prefect helps your code automatically retry on failure. 

### Notifications
You can easily set up e-mail or Slack notifications so that the right people are notified when something doesn't go as planned. 

### Designed for performance
Prefect 2.0 has been designed from the ground up to handle the dynamic, scalable workloads that today's dataflows demands. 

### Integrates with other modern data tools
Prefect has [integrations](collections/overview/) for all the major cloud providers and modern data tools such as Snowflake, Databricks, dbt, Airbyte, and Fivetran. 

### Async and parallelization options
Prefect provides [concurrency and sequential execution options](concepts/task-runners/). With a single import and one argument to your flow decorator you can set up parallel processing across clusters with Dask and Ray integrations. 

### Works well with containers
Prefect is often used with [Docker and Kubernetes](concepts/deployments/#packaging-flows). Prefect can even package your flow directly into a Docker image. 

### Security first
Prefect helps you keep your data and code secure. Prefect's patented [hybrid execution model](https://www.prefect.io/why-prefect/hybrid-model/) means your data can stay in your environment while Prefect Cloud orchestrates your flows. Prefect the company is SOC2 compliant and our enterprise product makes it easy for you to restrict access to the right people in your organization.

### Faster and easier than building from scratch
It's estimated that up to 80% of a data engineer's time is spent writing code to guard against edge cases and provide information when a dataflow inevitably fails. Building the functionality that Prefect 2.0 delivers by hand would be a significant cost of engineering time. 

Plug Prefect 2.0 into your existing code and you can move faster with greater confidence in your dataflows!

### Flexible 
Some workflow tools require you to make DAGs (directed acyclic graphs). DAGs represent a rigid framework that is overly constraining for modern, dynamic dataflows. Prefect 2.0 allows you to create dynamic dataflows in native Python - no DAGs required. 

### Incremental adoption
Prefect 2.0 is designed for incremental adoption. You can decorate as many of your dataflow functions as you like and get all the benefits of Prefect as you go!

## How to get started

Read the docs, run the code, and join 20,000 thousand community members in [our Slack community](https://www.prefect.io/slack). Thank you for being part of the mission to coordinate the world's dataflow and, of course, **happy engineering!**

!!! info "Don't Panic"
    Prefect 2.0 is under active development and may change rapidly. For production use, we recommend [Prefect 1.0](https://github.com/prefecthq/prefect).
---

## Examples

### Parallel execution

Control the task execution environment by changing a flow's `task_runner`. 
The tasks in this flow, using the `DaskTaskRunner`, will automatically be submitted to run in parallel on a [Dask.distributed](http://distributed.dask.org/) cluster:

```python hl_lines="2 11"
from prefect import flow, task
from prefect.task_runners import DaskTaskRunner
import httpx

@task(retries=3)
def get_stars(repo):
    url = f"https://api.github.com/repos/{repo}"
    count = httpx.get(url).json()["stargazers_count"]
    print(f"{repo} has {count} stars!")

@flow(name="GitHub Stars", task_runner=DaskTaskRunner())
def github_stars(repos):
    for repo in repos:
        get_stars(repo)

# run the flow!
if __name__ == "__main__":
    github_stars(["PrefectHQ/Prefect", "PrefectHQ/miter-design"])
```

### Async concurrency

Prefect 2.0 ships with native async support. 
Flows can include a mix of synchronous and asynchronous tasks, just like Python.

```python hl_lines="3 6-8 13-14 17"
from prefect import flow, task
import httpx
import asyncio

@task(retries=3)
async def get_stars(repo):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.github.com/repos/{repo}")
    count = response.json()["stargazers_count"]
    print(f"{repo} has {count} stars!")

@flow(name="GitHub Stars")
async def github_stars(repos):
    await asyncio.gather(*[get_stars(repo) for repo in repos])

# run the flow!
asyncio.run(github_stars(["PrefectHQ/Prefect", "PrefectHQ/miter-design"]))
```

The above examples are just scratching the surface of how Prefect can help you coordinate your dataflows.

---

## Next steps

Prefect 2.0 was designed for incremental adoption into your workflows. Our documentation is organized to support your exploration. Here are a few sections you might find helpful:

### Getting started

Begin by [installing Prefect 2.0](getting-started/installation.md) on your machine, then follow one of our [friendly tutorials](tutorials/first-steps) to learn by example. See the [Getting Started overview](getting-started/overview) for more.

### Concepts

Learn more about Prefect 2.0's features and design by reading our in-depth [concept docs](concepts/overview.md). The concept docs are intended to introduce the building blocks of Prefect, build up to orchestration and deployment, and finally cover some of the advanced use cases that Prefect makes possible.

### Prefect UI & Prefect Cloud

See how [Prefect's UI and cloud hosted functionality](ui/overview/) can make orchestrating dataflows a joy.

### Collections

Prefect integrates with the other tools of the modern data stack. In our [collections docs](collections/overview) learn about our pre-built integrations and see how to add your own.

### Frequently asked questions

Prefect 2.0 represents a fundamentally new way of building and orchestrating dataflows. Learn more about common questions by reading our [FAQ](faq.md).

### API reference

Prefect 2.0 provides a number of programmatic workflow interfaces, each of which is documented in the [API Reference](api-ref/overview). This section is where you can learn how a specific function works, or see the expected payload for a REST endpoint.

## Join the community

Prefect 2.0 was made possible by the fastest-growing community of data practitioner. The [Prefect Slack community](https://prefect.io/slack) is a fantastic place to learn more, ask questions, or get help with workflow design. The [Prefect Discourse](https://discourse.prefect.io/) is an additional community-driven knowledge base to find answers to your Prefect-related questions. Join us and thousands of friendly data folks to learn how to coordinate your dataflows with Prefect.
