---
icon: material/star-shooting-outline
description: Get started with Prefect, the easiest way to orchestrate and observe your data pipelines
tags:
    - getting started
    - quick start
    - overview
hide:
  - toc
---

# Welcome to Prefect: The easiest way to orchestrate and observe your data pipelines

"Everything fails all the time" - AWS CTO, Werner Vogels 

If you move data, these failures can be costly in terms of time, money, and frustration. Prefect makes it better with:

<ul class="ul-line-height-compress">
    <li> <a href="/concepts/schedules"> scheduling </a> </li>
    <li> <a href="/concepts/tasks/#task-arguments"> retries </a> </li>
    <li> <a href="/concepts/logs/"> logging </a> </li>
    <li> <a href="/concepts/tasks/#caching"> caching</a> </li>
    <li> <a href="/ui/notifications/"> notifications</a> </li>
    <li> <a href="/ui/overview/"> observability</a> </li>
</ul>

Trying to implement these features for your workflows on your own is a huge pain that takes a lot of time &mdash; time that could be better used writing domain-specific code. That's why Prefect offers all this functionality and more! 

Prefect makes it easy for you to bring your Python code, sprinkle in a few decorators, and go!

---

## Quick Start: Hello Prefect

In your Python virtual environment, [Install Prefect](/getting-started/installation/) with `pip install prefect`. 

## Run a basic flow

Import `flow` and decorate your Python function using the [`@flow`][prefect.flows.flow] decorator.

```python
from prefect import flow

@flow
def my_favorite_function():
    print("What is your favorite number?")
    return 42

print(my_favorite_function())
```

Run the code and you should see output like this:


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

The Prefect orchestration engine observes the flow run state and saves it for you in a database. TK link to db By adding a single decorator, you got observation capabilities. There's much more you can do with Prefect, so keep rolling!

---

## Next Steps

3 buttons next to each other -mobile responsive - can I use bootstrap type classes? TK
[Tutorial](/tutorial/index/)    [Concepts](/concepts/index/)  [Guides](guides/index/)

---

## Community

- Join over 25,000 engineers in the [Prefect Slack community](https://prefect.io/slack)
- Get help in [Prefect Discourse](https://discourse.prefect.io/) - the community-driven knowledge base
- [Give Prefect a ⭐️ on GitHub](https://github.com/PrefectHQ/prefect) TK display social proof with count of github stars - mabye use badges.io

---


!!! tip "Changing from 'Orion'"
    With the 2.8.1 release, **we removed references to "Orion" and replaced them with more explicit, conventional nomenclature throughout the codebase**. These changes clarify the function of various components, commands, and variables. See the [Release Notes](https://github.com/PrefectHQ/prefect/blob/main/RELEASE-NOTES.md#release-281) for details.

!!! help "Looking for Prefect 1 Core and Server?"
    Prefect 2 is now available for general use. See our [Migration Guide](guides/migration-guide/) to move your flows from Prefect 1 to Prefect 2.

    [Prefect 1 Core and Server documentation](http://docs-v1.prefect.io/) is available at [http://docs-v1.prefect.io/](http://docs-v1.prefect.io/).