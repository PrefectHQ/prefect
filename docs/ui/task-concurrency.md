---
description: Configure task run concurrency from the Prefect UI and Prefect Cloud.
tags:
    - UI
    - task runs
    - concurrency
    - concurrency limits
    - task concurrency
    - Prefect Cloud
---

# Task Run Concurrency

There are situations in which you want to restrict the number of certain tasks that can run simultaneously. For example, if many tasks across multiple flows are designed to interact with a database that only allows 10 connections, you want to make sure that no more than 10 tasks that connect to this database are running at any given time.

Prefect has built-in functionality for achieving this: [task run concurrency limits](/concepts/tasks/#task-run-concurrency-limits).

You may configure task concurrency limits via the UI as described here, or via the Prefect [CLI](/concepts/tasks/#cli) or [Python client](/concepts/tasks/#python-client).

Task run concurrency limits use [task tags](/concepts/tasks/#tags). You can specify an optional concurrency limit as the maximum number of concurrent task runs in a `Running` state for tasks with a given tag. The specified concurrency limit applies to any task to which the tag is applied.

If a task has multiple tags, it will run only if _all_ tags have available concurrency. 

Tags without explicit limits are considered to have unlimited concurrency.

!!! note "0 concurrency limit aborts task runs"
    Currently, if the concurrency limit is set to 0 for a tag, any attempt to run a task with that tag will be aborted instead of delayed.

### Configuring concurrency limits

On the **Task Run Concurrency** page, you can set concurrency limits on as few or as many tags as you wish. 

![Viewing task run concurrency limits in the Prefect UI](../img/ui/task-run-concurrency.png)

Select the **+** button to create a new task run concurrency limit. You'll be able to specify the tag and maximum number of concurrent task runs.

![Adding a new task run concurrency limit in the Prefect UI](../img/ui/add-concurrency-limit.png)
