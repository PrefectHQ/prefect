---
icon: material/brain
description: Learn about Prefect concepts.
tags:
    - concepts
    - features
    - overview
---

# Explore Prefect concepts

## Develop

| Keyword                                     | Description                                                                                                                                                                        |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| __[Flows](flows.md)__                       | The most basic Prefect objects.                                                                                                                                                      |
| __[Tasks](tasks.md)__                       | Discrete units of work in a Prefect workflow.                                                                                                                                      |
| __[Results](results.md)__                   | The data returned by a flow or a task.                                                                                                                                   |
| __[Artifacts](artifacts.md)__               | Persisted outputs for human viewing such as tables or links.                                                                                                                              |
| __[States](states.md)__                     | Contain information about the status of a particular task run or flow run.                                                                                    |
| __[Task Runners](task-runners.md)__         | enable you to engage specific executors for Prefect tasks, such as for concurrent, parallel, or distributed execution of tasks                                                     |
| __[Runtime Context](runtime-context.md)__   | Prefect tracks information about the current flow or task run with a run context                                                                                                   |
| __[Profiles & Configuration](settings.md)__ | Prefect settings and configuration                                                                                                                                                 |
| __[Blocks](blocks.md)__                     | Blocks are a primitive within Prefect that enable the storage of configuration and provide an interface for interacting with external systems                                      |
| __[Variables](variables.md)__               | Variables enable you to store and reuse non-sensitive bits of data, such as configuration information. Variables are named, mutable string values, much like environment variables |

## Deploy
| Keyword                                           | Description                                                                                              |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| __[Deployments](deployments.md)__                 | are a server-side concept that encapsulates a flow, allowing it to be scheduled and triggered via API    |
| __[Projects](projects.md)__                       | are a minimally opinionated set of files that describe how to prepare one or more flow deployments       |
| __[Work Pools, Workers & Agents](work-pools.md)__ | bridge the Prefect orchestration environment with your execution environment                             |
| __[Storage](storage.md)__                         | Lets you configure how flow code for deployments is persisted and retrieved by Prefect agents.            |
| __[Filesystems](filesystems.md)__                 | [Blocks](/concepts/blocks/) that allow you to read and write data from paths.                                |
| __[Infrastructure](infrastructure.md)__           | are [Blocks](blocks.md) which specify infrastructure for flow runs created by the deployment at runtime. |
| __[Schedules](schedules.md)__                     | tell the Prefect API how to create new flow runs for you automatically on a specified cadence.           |
__[Logging](logs.md)__
Log a variety of useful information about your flow and task runs on the server.

Features specific to [Prefect Cloud](../cloud/) are in their own subheading.
