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

|                                         |                                                                                                                                             |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| [Flows](flows.md)                       | The most basic Prefect object                                                                                                               |
| [Tasks](tasks.md)                       | Discrete units of work in a Prefect workflow                                                                                                |
| [Results](results.md)                   | Results represent the data returned by a flow or a task                                                                                     |
| [Artifacts](artifacts.md)               | Artifacts are persisted outputs such as tables, files, or links                                                                             |
| [States](states.md)                     | States are rich objects that contain information about the status of a particular task run or flow run                                      |
| [Task Runners](task-runners.md)         | Task runners enable you to engage specific executors for Prefect tasks, such as for concurrent, parallel, or distributed execution of tasks |
| [Runtime Context](runtime-context.md)   | Prefect tracks information about the current flow or task run with a run context                                                            |
| [Profiles & Configuration](settings.md) | Prefect settings and configuration                                                                                                          |
| [Blocks](blocks.md)       | Blocks are a primitive within Prefect that enable the storage of configuration and provide an interface for interacting with external systems                                      |
| [Variables](variables.md) | Variables enable you to store and reuse non-sensitive bits of data, such as configuration information. Variables are named, mutable string values, much like environment variables |

## Deploy
|||
|-|-|
|[Deployments](deployments.md)|Deployments are a server-side concept that encapsulates a flow, allowing it to be scheduled and triggered via API|
|[Projects](projects.md)|A project is a minimally opinionated set of files that describe how to prepare one or more flow deployments|
|[Work Pools, Workers & Agents](work-pools.md)|Work pools and the services that poll them, workers and agents, bridge the Prefect orchestration environment with your execution environment|
|[Storage](storage.md)|Storage lets you configure how flow code for deployments is persisted and retrieved by Prefect agents|
|[Filesystems](filesystems.md)|A filesystem block is an object that allows you to read and write data from paths|
|[Infrastructure](infrastructure.md)|Infrastructure blocks specify infrastructure for flow runs created by the deployment at runtime.|
|[Schedules](schedules.md)|Schedules tell the Prefect API how to create new flow runs for you automatically on a specified cadence.|
|[Logging](logs.md)|Prefect enables you to log a variety of useful information about your flow and task runs|

Features specific to [Prefect Cloud](../cloud/) are in their own subheading.
