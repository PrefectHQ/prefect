---
icon: material/star-shooting-outline
title: Welcome to Prefect
description: Get started with Prefect, the easiest way to orchestrate and observe your data pipelines
tags:
    - getting started
    - quick start
    - overview
hide:
  - toc
---


# **Welcome to Prefect**

Prefect enables you to build and observe resilient data workflows so that you can understand, react to, and recover from unexpected changes. It's the easiest way to transform any Python function into a unit of work that can be observed and orchestrated. Just bring your Python code, sprinkle in a few decorators, and go!

With Prefect you gain simple:

<ul class="ul-line-height-compress" style="columns: 2">
    <li> <a href="/concepts/schedules"> scheduling </a> </li>
    <li> <a href="/concepts/tasks/#task-arguments"> retries </a> </li>
    <li> <a href="/concepts/logs/"> logging </a> </li>
    <li> <a href="/concepts/tasks/#caching"> caching</a> </li>
    <li> <a href="/concepts/task-runners/#task-runners"> async</a> </li>
    <li> <a href="/ui/notifications/"> notifications</a> </li>
    <li> <a href="/ui/overview/"> observability</a> </li>
</ul>

Trying to implement these features from scratch is a huge pain that takes time, headaches, and money. That's why Prefect offers all this functionality and more!

<figure markdown>
![screenshot of Cloud UI timeline view with menu](img/ui/flow-run-page.png)
<figcaption>Prefect UI</figcaption>
</figure>

#### New to Prefect?
If you're ready to dive in and learn Prefect, check out the Prefect [concepts](/concepts/index/) and try some [tutorials](/tutorials/) to see how they work in action.

For deeper dives on specific topics, explore our [guides](guides/index/) for common use-cases. <div style="height: 10px"></div>

[Concepts](/concepts){ .md-button .main-button--secondary .full } [Tutorials](/tutorials/){ .md-button .md-button--primary .main-button--primary .full }  [Guides](guides){ .md-button .main-button--secondary .full }

<div style="height: 10px"></div>
<p>Or, read on for a quick sample of Prefect.</p>
---

## Quick Start: Hello Prefect

Install Prefect with 

<div class="terminal">
```bash
pip install -U prefect
```
</div>

See the [install guide](/getting-started/installation/) for more detailed instructions.

### Run a basic flow

Import `flow` and decorate your Python function using the [`@flow`][prefect.flows.flow] decorator.

```python hl_lines="1 3"
from prefect import flow

@flow
def my_favorite_function():
    print("What is your favorite number?")
    return 42

print(my_favorite_function())
```

Thats it! Your function is now a flow. Run the code as you normally would, and you'll see its execution via the Prefect logs:

<div class="terminal">
```bash
$ python hello_prefect.py
15:27:42.543 | INFO    | prefect.engine - Created flow run 'olive-poodle' for flow 'my-favorite-function'
15:27:42.543 | INFO    | Flow run 'olive-poodle' - Using task runner 'ConcurrentTaskRunner'
What is your favorite number?
15:27:42.652 | INFO    | Flow run 'olive-poodle' - Finished in state Completed()
42
```
</div>

Prefect automatically persists all executions of your flow along with useful metadata such as start time, end time, and state. This is just the beginning, so keep exploring to learn how to add retries, notifications, scheduling and much more!

## Next Steps
To learn more, try our [tutorials](/tutorials) and [guides](/guides), or go deeper with [Prefect concepts](/concepts).

---

## Community

- Join over 25,000 engineers in the [Prefect Slack community](https://prefect.io/slack)
- Get help in [Prefect Discourse](https://discourse.prefect.io/) - the community-driven knowledge base
- [Give Prefect a ⭐️ on GitHub](https://github.com/PrefectHQ/prefect) 

---

!!! tip "Changing from 'Orion'"
    With the 2.8.1 release, **we removed references to "Orion" and replaced them with more explicit, conventional nomenclature throughout the codebase**. These changes clarify the function of various components, commands, and variables. See the [Release Notes](https://github.com/PrefectHQ/prefect/blob/main/RELEASE-NOTES.md#release-281) for details.

!!! help "Looking for Prefect 1 Core and Server?"
    Prefect 2 is now available for general use. See our [Migration Guide](guides/migration-guide/) to move your flows from Prefect 1 to Prefect 2.

    [Prefect 1 Core and Server documentation](http://docs-v1.prefect.io/) is available at [http://docs-v1.prefect.io/](http://docs-v1.prefect.io/).
