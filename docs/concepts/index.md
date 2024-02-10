---
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

| Concept                                            | Description                                                                                                                 |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| __[Flows](/concepts/flows)__                       | A Prefect workflow, defined as a Python function.             |
| __[Tasks](/concepts/tasks)__                       | Discrete units of work in a Prefect workflow.                |
| __[Deployments](/concepts/deployments)__           | A server-side concept that encapsulates flow metadata, allowing it to be scheduled and triggered via API. |
| __[Work Pools & Workers](/concepts/work-pools)__   | Use Prefect to dynamically provision and configure infrastructure in your execution environment.    |
| __[Schedules](/concepts/schedules)__               | Tell the Prefect API how to create new flow runs for you automatically on a specified cadence.     |
| __[Results](/concepts/results)__                   | The data returned by a flow or a task.                                 |
| __[Artifacts](/concepts/artifacts)__               | Formatted outputs rendered in the Prefect UI, such as markdown, tables, or links.  
| __[States](/concepts/states)__                     | Rich objects that capture the status of a particular task run or flow run.                                                                            |
| __[Blocks](/concepts/blocks)__                     | Prefect primitives that enable the storage of configuration and provide a UI interface.          |
| __[Task Runners](/concepts/task-runners)__         | Configure how tasks are run - concurrently, in parallel, or in a distributed environment. |
| __[Automations](/concepts/automations)__           | Configure actions that Prefect executes automatically based on trigger conditions.         |

|  Block and Agent-Based Deployments                 | Description   |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| __[Block-based Deployments](/concepts/deployments-block-based)__    | Create deployments that rely on blocks.   |
| __[Infrastructure](/concepts/infrastructure)__           | Blocks that specify infrastructure for flow runs created by a deployment.   |
| __[Storage](/concepts/storage)__                         | Lets you configure how flow code for deployments is persisted and retrieved.     |
| __[Agents](/concepts/agents)__                           | Like untyped workers. |

Many features specific to [Prefect Cloud](/cloud/) are in their own navigation subheading.
