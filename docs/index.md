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

Prefect 2.0 makes it easy to decorate your existing Python functions and provide you with retries, caching, and dynamic workflows. 

### A user friendly GUI 
In the Prefect Orion UI you can quickly set up notifications, visualize run history, and inspect logs.  

### Faster and easier than building from scratch
Building this kind of functionality from scratch is a huge pain. It's estimated that up to 80% of a data engineer's time is spent writing code to guard against edge cases and provide information when a dataflow inevitably fails. Prefect 2.0 helps eliminate this negative engineering, so you can do more faster with confidence in your dataflows.

### Designed for performance
Prefect 2.0 has been designed from the ground up to handle the dynamic, scalable workloads that today's dataflows demands. 

### Integrates with other modern tools
Prefect integrates with all the major cloud providers and modern data stack tools such as Snowflake, Databricks, dbt, Airbyte, and Fivetran. Prefect uses concurrency by default and you can set up parallel processing across clusters with our Dask and Ray integrations. Prefect is often used with Docker and Kubernetes.

### Security first
Prefect helps you keep your data and code secure. Prefect's hybrid execution model means your data can stay in your environment while Prefect Cloud orchestrates your flows. Prefect the company is SOC2 compliant and our enterprise product makes it easy for you to restrict access to the right people in your organization.

### Flexible and easy to start
You don’t need to rewrite your entire dataflow as a directed acyclic graph (DAG) to take advantage of Prefect 2.0. DAGs represent a rigid framework that is overly constraining for modern, dynamic dataflows. Instead, you can incrementally adopt Prefect 2.0 for dynamic dataflows.

## How to get started

Read the docs, run the code, and join 20,000 thousand community members in [our Slack community](https://www.prefect.io/slack). Thank you for being part of the mission to coordinate the world's dataflow and, of course, **happy engineering!**

!!! info "Don't Panic"
    Prefect 2.0 is under active development and may change rapidly. For production use, we recommend [Prefect 1.0](https://github.com/prefecthq/prefect).
---

### Basic coordination

The code below fetches data on GitHub stars. Add the three highlighted lines of code to your functions and you're off to the races. 


```python hl_lines="1 5 11"
from prefect import flow, task
from typing import List
import httpx

@task(retries=3)
def get_stars(repo: str):
    url = f"https://api.github.com/repos/{repo}"
    count = httpx.get(url).json()["stargazers_count"]
    print(f"{repo} has {count} stars!")

@flow(name="GitHub Stars")
def github_stars(repos: List[str]):
    for repo in repos:
        get_stars(repo)

# run the flow!
github_stars(["PrefectHQ/Prefect", "PrefectHQ/miter-design"])
```

By adding `retries=3 ` to the `task` decorator, the `get_stars` function will automatically rerun up to three times on failure.

### Observe in the Prefect Orion UI dashboard 
Fire up the UI locally to visualize the task run history and gain insight into their execution:

```bash
prefect orion start
```

![](./img/ui/orion-dashboard.png)

From here, you can continue to use Prefect interactively, set up automated [deployments](concepts/deployments.md), or move to the hosted Prefecct Cloud.

### Parallel execution

Control the task execution environment by changing a flow's `task_runner`. The tasks in this flow, using the `DaskTaskRunner`, will automatically be submitted to run in parallel on a [Dask.distributed](http://distributed.dask.org/) cluster:

```python hl_lines="2 12"
from prefect import flow, task
from prefect.task_runners import DaskTaskRunner
from typing import List
import httpx

@task(retries=3)
def get_stars(repo: str):
    url = f"https://api.github.com/repos/{repo}"
    count = httpx.get(url).json()["stargazers_count"]
    print(f"{repo} has {count} stars!")

@flow(name="GitHub Stars", task_runner=DaskTaskRunner())
def github_stars(repos: List[str]):
    for repo in repos:
        get_stars(repo)

# run the flow!
if __name__ == "__main__":
    github_stars(["PrefectHQ/Prefect", "PrefectHQ/miter-design"])
```

### Async concurrency

Prefect 2.0 ships with native async support. Flows can include a mix of synchronous and asynchronous tasks, just like Python.

```python hl_lines="4 7-9 14-15 18"
from prefect import flow, task
from typing import List
import httpx
import asyncio

@task(retries=3)
async def get_stars(repo: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.github.com/repos/{repo}")
    count = response.json()["stargazers_count"]
    print(f"{repo} has {count} stars!")

@flow(name="GitHub Stars")
async def github_stars(repos: List[str]):
    await asyncio.gather(*[get_stars(repo) for repo in repos])

# run the flow!
asyncio.run(github_stars(["PrefectHQ/Prefect", "PrefectHQ/miter-design"]))
```

The above examples are just scratching the surface of how Prefect can help you coordinate your dataflows.

## Next steps

Prefect 2.0 was designed for incremental adoption into your workflows. Our documentation is organized to support your exploration. Here are a few sections you might find helpful:

### Getting started

Begin by [installing Prefect 2.0](getting-started/installation.md) on your machine, then follow one of our [friendly tutorials](tutorials/first-steps) to learn by example. See the [Getting Started overview](getting-started/overview) for more.

### Concepts

Learn more about Prefect 2.0's features and design by reading our in-depth [concept docs](concepts/overview.md). The concept docs are intended to introduce the building blocks of Prefect, build up to orchestration and deployment, and finally cover some of the advanced use cases that Prefect makes possible.

### Prefect UI & Prefect Cloud

See how [Prefect's GUI and cloud hosted functionality](ui/overview/) can make orchestrating dataflows a joy.

### Collections

Prefect integrates with the other tools of the modern data stack. In our [collections docs](collections/overview) learn about our pre-built integrations and see how to add your own.

### Frequently asked questions

Prefect 2.0 represents a fundamentally new way of building and orchestrating dataflows. Learn more about common questions by reading our [FAQ](faq.md).

### API reference

Prefect 2.0 provides a number of programmatic workflow interfaces, each of which is documented in the [API Reference](api-ref/overview). This section is where you can learn how a specific function works, or see the expected payload for a REST endpoint.

## Join the community

Prefect 2.0 was made possible by the fastest-growing community of data practitioner. The [Prefect Slack community](https://prefect.io/slack) is a fantastic place to learn more, ask questions, or get help with workflow design. The [Prefect Discourse](https://discourse.prefect.io/) is an additional community-driven knowledge base to find answers to your Prefect-related questions. Join us and thousands of friendly data folks to learn how to coordinate your dataflows with Prefect.
