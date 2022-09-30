---
description: Take a deeper dive into the features of Prefect 2.
tags:
    - concepts
    - features
    - overview
---

# Concepts Overview

Getting started building and running workflows with Prefect doesn't require much more than a knowledge of Python and an intuitive understanding of "tasks" and "flows".  However, deploying and scheduling workflows as well as more advanced usage patterns do require a deeper understanding of the building blocks of Prefect.

These guides are intended to provide the reader with a deeper understanding of how the system works and how it can be used to its full potential; in addition, these guides can be revisited as reference material as you learn more.

## Building Blocks

The fundamental building blocks of Prefect are [flows](/concepts/flows/) and [tasks](/concepts/tasks/).  We recommend all readers begin by understanding these concepts first. 

## Deployment and Orchestration 

If you are looking to configure the rules that govern your tasks' state transitions, or better understand how runs are orchestrated in the backend, then diving into [states](/concepts/states/), [logs](/concepts/logs/) and the [Prefect UI](/ui/overview/) or [Prefect Cloud](/ui/cloud/) should help orient you.

Once you are comfortable writing and running workflows interactively or manually via scripts, you will most likely want to package and "deploy" them, which enables you to create flow runs in other execution environments, via the UI, API, or schedules. Deploying a workflow in Prefect requires understanding: 

- [Deployments](/concepts/deployments/)
- [Storage](/concepts/storage/)
- [Work queues & agents](/concepts/work-queues/)
- [Scheduling](/concepts/schedules/)

## Advanced Concepts

More advanced use cases require understanding the internals of the system. Begin by diving into [settings](settings.md) to understand the configuration options available to you. You may also want to learn more about the Prefect Orion [database](/concepts/database/), which is used to persist data about flow and task run state, run history, logs, and more.
