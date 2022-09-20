---
description: Learn about Prefect 2, our second-generation workflow coordination and orchestration engine.
tags:
    - getting started
    - overview
---

# Welcome to Prefect 2

!!! help "Looking for Prefect 1 Core and Server?"
    Prefect 2 is now available for general use. See our [Migration Guide](/migration-guide/) to move your flows from Prefect 1 to Prefect 2.

    If you're looking for the [Prefect 1 Core and Server documentation](http://docs-v1.prefect.io/), they're available at [http://docs-v1.prefect.io/](http://docs-v1.prefect.io/).

## Prefect coordinates your dataflow

Prefect is [air traffic control for the modern data stack](https://www.prefect.io/guide/blog/the-global-coordination-plane#ATCfortheMDS). Monitor, coordinate, and orchestrate dataflows between and across your applications. Build pipelines, deploy them anywhere, and configure them remotely. You might just love your workflows again.

## Why Prefect?

If you move data, you probably need the following functionality:

- [scheduling](concepts/schedules/)
- [retries](concepts/tasks/#task-arguments)
- [logging](concepts/logs/)
- [caching](concepts/tasks/#caching)
- [notifications](ui/notifications/)
- [observability](/ui/overview/)

Implementing all of these features for your dataflows is a huge pain that takes a lot of time &mdash; time that could be better used writing domain-specific code.

That's why Prefect 2 offers all this functionality and more! 

## Getting started with Prefect

Prefect 2 was designed for incremental adoption into your workflows. The documentation is organized to support your exploration. Here are a few sections you might find helpful:

**Getting started**

Begin by [installing Prefect 2](/getting-started/installation/) on your machine, then follow one of our [friendly tutorials](/tutorials/first-steps/) to learn by example. See the [Getting Started overview](/getting-started/overview/) for more.

Even if you have used Prefect 1 ("Prefect Core") and are familiar with Prefect workflows, we still recommend reading through these first steps. Prefect 2 offers significant new functionality.


**Concepts**

Learn more about Prefect 2's features and design by reading our in-depth [concept docs](/concepts/overview/). The concept docs are intended to introduce the building blocks of Prefect, build up to orchestration and deployment, and finally cover some of the advanced use cases that Prefect makes possible.

**Prefect UI & Prefect Cloud**

See how [Prefect's UI and cloud hosted functionality](/ui/overview/) can make coordinating dataflows a joy.

**Collections**

Prefect integrates with the other tools of the modern data stack. In our [collections docs](/collections/overview/) learn about our pre-built integrations and see how to add your own.

**Frequently asked questions**

Prefect 2 represents a fundamentally new way of building and orchestrating dataflows. You can find responses to common questions by reading our [FAQ](/faq/) and checking out the [Prefect Discourse](https://discourse.prefect.io/).

**API reference**

Prefect 2 provides a number of programmatic workflow interfaces, each of which is documented in the [API Reference](/api-ref/overview). This section is where you can learn how a specific function works, or see the expected payload for a REST endpoint.

**Contributing**

Learn how [you can get involved](/contributing/overview/).

Prefect 2 is made possible by the fastest-growing community of data practitioners. The [Prefect Slack community](https://prefect.io/slack) is a fantastic place to learn more, ask questions, or get help with workflow design. 

The [Prefect Discourse](https://discourse.prefect.io/) is an additional community-driven knowledge base to find answers to your Prefect-related questions. 

## Prefect highlights

**Graceful failures**

Inevitably dataflows will fail. Prefect helps your code automatically retry on failure. 

**Notifications**

You can easily set up e-mail or Slack notifications so that the right people are notified when something doesn't go as planned. 

**Designed for performance**

Prefect 2 has been designed from the ground up to handle the dynamic, scalable workloads that today's dataflows demands. 

**Integrates with other modern data tools**

Prefect has [integrations](/collections/overview/) for all the major cloud providers and modern data tools such as Snowflake, Databricks, dbt, and Airbyte. 

**Simple concurrency**

Prefect makes it easy to run your code [asynchronously](concepts/task-runners/). Prefect allows you to write workflows mixing synchronous and asynchronous tasks without worrying about the complexity of managing event loops.

**Easy distributed parallel processing**

Prefect makes it easy to send tasks to remote clusters for distributed parallel processing with [Dask](https://github.com/PrefectHQ/prefect-dask) and [Ray](https://github.com/PrefectHQ/prefect-ray) integrations. 

**Works well with containers**

Prefect is often used with [Docker and Kubernetes](/concepts/deployments/). 

**Security first**

Prefect helps you keep your data and code secure. Prefect's patented [hybrid execution model](https://www.prefect.io/why-prefect/hybrid-model/) means:

- **(OSS)** Prefect's orchestration and execution layers can be managed independently
- **(Cloud)** your data can stay in your environment while Prefect Cloud manages orchestration of your dataflow

Prefect Technologies is SOC2 Type II compliant and our enterprise product makes it easy for you to restrict access to the right people in your organization.

**A user friendly, interactive dashboard for your dataflows**

In the [Prefect Orion UI](/ui/overview/) you can quickly set up notifications, visualize run history, and schedule your dataflows.  

**Faster and easier than building from scratch**

It's estimated that up to 80% of a data engineer's time is spent writing code to guard against edge cases and provide information when a dataflow inevitably fails. Building the functionality that Prefect 2 delivers by hand would be a significant cost of engineering time. 

**Flexible** 

Some workflow tools require you to make DAGs (directed acyclic graphs). DAGs represent a rigid framework that is overly constraining for modern, dynamic dataflows. Prefect 2 allows you to create dynamic dataflows in native Python - no DAGs required. 

**Incremental adoption**

Prefect 2 is designed for incremental adoption. You can decorate as many of your dataflow functions as you like and get all the benefits of Prefect as you go!

## Prefect in action

To dive right in and see what Prefect 2 can do, simply sprinkle in a few decorators and add a little configuration, like the example below. 

### Basic example

This code fetches data about GitHub stars for a few repositories. Add the three highlighted lines of code to your functions to use Prefect, and you're off to the races! 


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
github_stars(["PrefectHQ/Prefect", "PrefectHQ/prefect-aws",  "PrefectHQ/prefect-dbt"])
```

Run the code:

```bash
python github_stars_example.py
```

And see the logger's output in your terminal:

```bash
10:56:06.988 | INFO    | prefect.engine - Created flow run 'grinning-crab' for flow 'github-stars'
10:56:06.988 | INFO    | Flow run 'grinning-crab' - Using task runner 'ConcurrentTaskRunner'
10:56:06.996 | WARNING | Flow run 'grinning-crab' - No default storage is configured on the server. Results from this flow run will be stored in a temporary directory in its runtime environment.
10:56:07.027 | INFO    | Flow run 'grinning-crab' - Created task run 'get_stars-2ca9fbe1-0' for task 'get_stars'
PrefectHQ/Prefect has 9579 stars!
10:56:07.190 | INFO    | Task run 'get_stars-2ca9fbe1-0' - Finished in state Completed()
10:56:07.199 | INFO    | Flow run 'grinning-crab' - Created task run 'get_stars-2ca9fbe1-1' for task 'get_stars'
PrefectHQ/prefect-aws has 7 stars!
10:56:07.327 | INFO    | Task run 'get_stars-2ca9fbe1-1' - Finished in state Completed()
10:56:07.337 | INFO    | Flow run 'grinning-crab' - Created task run 'get_stars-2ca9fbe1-2' for task 'get_stars'
PrefectHQ/prefect-dbt has 12 stars!
10:56:07.464 | INFO    | Task run 'get_stars-2ca9fbe1-2' - Finished in state Completed()
10:56:07.477 | INFO    | Flow run 'grinning-crab' - Finished in state Completed('All states completed.')
```

By adding `retries=3 ` to the `@task` decorator, the `get_stars` function automatically reruns up to three times on failure!

**Observe your flow runs in the Prefect UI**

Fire up the Prefect UI locally by entering this command in your terminal:

```bash
prefect orion start
```

Follow the link in your terminal to see the dashboard.

![screenshot of prefect orion dashboard with flow runs in a scatter plot](./img/intro-ui-dashboard.png)

Click on your flow name to see logs and other details.

![screenshot of prefect orion dashboard with logs, radar plot, and flow info](./img/intro-ui-logs.png)


The above example just scratch the surface of how Prefect can help you coordinate your dataflows.

## Next steps

Follow the [Getting Started docs](getting-started/overview/) and start building!

While you're at it [give Prefect a ⭐️ on GitHub](https://github.com/PrefectHQ/prefect) and join the thousands of community members in [our Slack community](https://www.prefect.io/slack). 

Thank you for joining our mission to coordinate the world's dataflow and, of course, **happy engineering!**
