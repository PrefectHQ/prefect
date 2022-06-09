---
description: Create and manage work queues from the Prefect UI and Prefect Cloud.
tags:
    - Orion
    - UI
    - deployments
    - flow runs
    - Prefect Cloud
    - work queues
    - agents
    - tags
---

# Work Queues

[Work Queues](/concepts/work-queues/) and agents work together to bridge your orchestration environment &mdash; a local Prefect API server or Prefect Cloud &mdash; and your execution environments. Work queues gather flow runs for scheduled deployments, and agents pick up work from their configured work queues.

Work queue configuration lets you specify which queues handle which flow runs. You can filter runs based on tags, flow runners, and even specific deployments.

You can create, edit, manage, and delete work queues through the Prefect API server, Prefect Cloud UI, or [Prefect CLI commands](/concepts/work-queues/#work-queue-configuration).

## Managing work queues

To manage work queues in the UI, click the **Work Queues** icon. This displays a list of currently configured work queues.

![The UI displays a list of configured work queues](/img/ui/work-queue-list.png)

You can also pause a work queue from this page by using the slider.

Select the **+** button to create a new work queue. You'll be able to specify the details for work served by this queue.

![Creating a new work queue in the Orion UI](/img/ui/work-queue-create.png)

Click on the name of any work queue to see details about it. 

![Viewing details of a work queue including agent configuration string](/img/ui/work-queue-details.png)

You can also pause a work queue from this page by using the slider.

The commands button enables you to edit or delete the work queue.