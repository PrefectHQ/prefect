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

## [Task Throttling](throttling.md)<Badge text="advanced" type="warn"/><Badge text="0.3.2+"/>
Learn how to use local parallelism for executing flows, and how to leverage _task throttling_ to prevent too many tasks from being executed simultaneously

## [Advanced Features](advanced-mapping.md)<Badge text="advanced" type="warn"/><Badge text="0.3.2+"/>
Dynamically create large numbers of tasks using `task.map()`! Using a real-world web-scraping project as an example, walks through the more advanced features of Prefect including advanced parameter usage, task mapping, parallelism and throttling. 

## [Migrating from Airflow](airflow_migration.md)<Badge text="advanced" type="warn"/><Badge text="0.3.2+"/>
Learn how to use Prefect to import, execute, extend and _improve_ your current Airflow DAGs!

## [Prefect Slack Integration](slack-notifications.md)<Badge text="0.3.2+"/>
Install the Prefect Slack integration and get real time notifications on the state of your tasks and flows -- all within the convenience of Slack!
