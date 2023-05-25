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
| __[Flows](/concepts/flows)__                       | A Prefect workflow, modeled as a Python function.                                                                                                                                               |
| __[Tasks](/concepts/tasks)__                       | Discrete units of work in a Prefect workflow.                                                                                                                                      |
| __[Results](/concepts/results)__                   | The data returned by a flow or a task.                                                                                                                                             |
| __[Artifacts](/concepts/artifacts)__               | Persisted outputs for human viewing such as tables or links.                                                                                                                       |
| __[States](/concepts/states)__                     | Contain information about the status of a particular task run or flow run.                                                                                                         |
| __[Task Runners](/concepts/task-runners)__         | Enable you to engage specific executors for Prefect tasks, such as concurrent, parallel, or distributed execution of tasks.                                                    |
| __[Runtime Context](/concepts/runtime-context)__   | Information about the current flow or task run that you can refer to in your code.        |
| __[Profiles & Configuration](/concepts/settings)__ | Settings you can use to interact with Prefect Cloud and a Prefect server.                                                                                                         |
| __[Blocks](/concepts/blocks)__                     | Prefect primitives that enable the storage of configuration and provide a UI interface.                                       |
| __[Variables](/concepts/variables)__               | Named, mutable string values, much like environment variables. |

## Deploy
| Keyword                                           | Description                                                                                           |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| __[Deployments](/concepts/deployments)__                 | A server-side concept that encapsulates a flow, allowing it to be scheduled and triggered via API. |
| __[Projects](/concepts/projects)__                       | A minimally opinionated set of files that describe how to prepare one or more flow deployments.    |
| __[Work Pools, Workers & Agents](/concepts/work-pools)__ | Bridge the Prefect orchestration environment with your execution environment.                          |
| __[Storage](/concepts/storage)__                         | Lets you configure how flow code for deployments is persisted and retrieved by Prefect agents.        |
| __[Filesystems](/concepts/filesystems)__                 | [Blocks](/concepts/blocks/) that allow you to read and write data from paths.                         |
| __[Infrastructure](/concepts/infrastructure)__           | [Blocks](/concepts/blocks/) that specify infrastructure for flow runs created by the deployment.              |
| __[Schedules](/concepts/schedules)__                     | Tell the Prefect API how to create new flow runs for you automatically on a specified cadence.        |
| __[Logging](/concepts/logs)__                            | Log a variety of useful information about your flow and task runs on the server.                      |

Features specific to [Prefect Cloud](/cloud/) are in their own subheading.
