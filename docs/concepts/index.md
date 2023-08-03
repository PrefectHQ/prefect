---
icon: material/brain
description: Learn about Prefect concepts.
tags:
    - concepts
    - features
    - overview
hide:
  - toc
search:
  boost: 2
---

# Explore Prefect concepts

## Develop

| Keyword                                            | Description                                                                                                                 |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| __[Flows](/concepts/flows)__                       | A Prefect workflow, modeled as a Python function.                                                                           |
| __[Tasks](/concepts/tasks)__                       | Discrete units of work in a Prefect workflow.                                                                               |
| __[Deployments](/concepts/deployments)__           | A server-side concept that encapsulates a flow, allowing it to be scheduled and triggered via API. |
| __[Work Pools & Workers](/concepts/work-pools)__   | Bridge the Prefect orchestration environment with your execution environment.                      |
| __[Schedules](/concepts/schedules)__               | Tell the Prefect API how to create new flow runs for you automatically on a specified cadence.     |
| __[Results](/concepts/results)__                   | The data returned by a flow or a task.                                                                                      |
| __[Artifacts](/concepts/artifacts)__               | Formatted outputs rendered in the Prefect UI, such as markdown, tables, or inks.                                      |
| __[States](/concepts/states)__                     | The status of a particular task run or flow run.                                                                            |
| __[Blocks](/concepts/blocks)__                     | Prefect primitives that enable the storage of configuration and provide a UI interface.                                     |
| __[Task Runners](/concepts/task-runners)__         | Enable you to engage specific executors for Prefect tasks, such as concurrent, parallel, or distributed execution of tasks. |
| __[Automations](/concepts/automations)__           | Configure actions that Prefect executes automatically based on trigger conditions.                |
| __[Filesystems](/concepts/filesystems)__           | Blocks that allow you to read and write data from paths.   |
|  Block and Agent-Based Deployments:                |    |
| __[Block-based Deployments](/concepts/deployments-block-based)__    | Create deployments that rely on blocks.   |
| __[Infrastructure](/concepts/infrastructure)__           | Blocks that specify infrastructure for flow runs created by a deployment.   |
| __[Storage](/concepts/storage)__                         | Lets you configure how flow code for deployments is persisted and retrieved.     |
| __[Agents](/concepts/agents)__                           | Like untyped workers. |

Many features specific to [Prefect Cloud](/cloud/) are in their own subheading.
