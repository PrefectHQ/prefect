# Concepts Overview

Getting started building and running workflows with Prefect doesn't require much more than a knowledge of Python and an intuitive understanding of "tasks" and "flows".  However, deploying and scheduling workflows as well as more advanced usage patterns do require a deeper understanding of the building blocks of Prefect.

These guides are intended to provide the reader with a deeper understanding of how the system works and how it can be used to its full potential; in addition, these guides can be revisited as reference material as you learn more.

## Building Blocks

The fundamental building blocks of Prefect are [flows](flows.md) and [tasks](tasks.md).  We recommend all readers begin by understanding these concepts first. 

## Deployment and Orchestration 

If you are looking to configure the rules that govern your tasks' state transitions, or better understand how runs are orchestrated in the backend then diving into [states](states.md) and [orchestration rules](orchestration.md) should help orient you.

Once you are comfortable writing and running workflows interactively and/or manually via scripts, you will most likely want to "deploy" them; deploying a workflow in Prefect requires understanding [deployments](deployments.md) and [scheduling](schedules.md).

## Advanced Concepts

More advanced use cases require understanding the internals of the system; dive in to [futures](futures.md) to understand the mechanics of task run execution and write advanced flow logic or [settings](settings.md) to understand the configuration options available to you.
