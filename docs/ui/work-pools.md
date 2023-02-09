---
description: Create and manage work pools from the Prefect UI and Prefect Cloud.
tags:
    - UI
    - deployments
    - flow runs
    - Prefect Cloud
    - work pools
    - agents
    - tags
---

# Work Pools

[Work Pools](/concepts/work-pools/) and agents work together to bridge your orchestration environment &mdash; a local Prefect server or Prefect Cloud &mdash; and your execution environments. Work pools gather flow runs for scheduled deployments, and agents pick up work from their configured work pool queues.

Work pool configuration lets you specify which queues handle which flow runs. You can filter runs based on tags and specific deployments.

You can create, edit, manage, and delete work pools through the Prefect API server, Prefect Cloud UI, or [Prefect CLI commands](/concepts/work-pools/#work-pool-configuration).

## Managing work queues

To manage work pools in the UI, click the **Work Pools** icon. This displays a list of currently configured work pools.

![The UI displays a list of configured work pools](../img/ui/work-pool-list.png)

You can also pause a work pool from this page by using the toggle.

Select the **+** button to create a new work pool. You'll be able to specify the details for work served by this work pool.

See the [Agents & Work Pools](/concepts/work-pools/) documentation for details on configuring agents and work pools, including creating work pools from the Prefect CLI.

Click on the name of any work pool to see details about it. This page includes the Prefect CLI command you can use to create an agent that pulls flow runs from this work pool.

You can also pause a work pool from this page by using the toggle.

The commands button enables you to edit or delete the work pool.