---
sidebarDepth: 0
---

# Contents

These tutorials are intended to help the reader get acquainted with the many features of Prefect and its vocabulary.  All code examples
are locally executable in any Python version supported by Prefect (3.4+).  Note that all features presented here are run without
the Prefect server.

## [ETL](etl.md)
The "hello, world!" of data engineering

## [Using Prefect as a Calculator](calculator.md)
Can your data engineering framework do this?

## [Task Retries](task-retries.md)
An overview of how Prefect handles retrying tasks

## [Triggers, Reference Tasks](triggers-and-references.md)
Overview of different triggers, such as `manual_only`, which allows for manual approval before a task can run.  Also covered: determining flow states using `reference_tasks`

## [Flow Visualization](visualization.md)
Visualize your Prefect flows with `flow.visualize()` and their local execution with the `BokehRunner`

## [Task Throttling](throttling.md)
Learn how to use local parallelism for executing flows, and how to leverage _task throttling_ to prevent too many tasks from being executed simultaneously
