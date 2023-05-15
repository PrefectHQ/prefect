---
icon: material/graph-outline
description: Learn the basics of creating and running Prefect flows and tasks.
tags:
    - tutorial
    - getting started
    - basics
    - tasks
    - flows
    - subflows
---
# Tutorial Overview

These tutorials provide examples of Prefect core concepts and step-by-step instructions on how to use them. For specific examples of how to perform more advanced tasks, check out our [guides](/guides/).

If you have used Prefect 1 ("Prefect Core") and are familiar with Prefect workflows, we still recommend reading through these first steps, particularly [Run a flow within a flow](/tutorials/first-steps/#run-a-flow-within-a-flow). Prefect 2 flows and subflows offer significant new functionality.

### Prerequisites

Before you start, install Prefect:

<div class="terminal">
```bash
pip install -U prefect
```
</div>

See the [install guide](/getting-started/installation/) for more detailed instructions.

### Tutorials
If you've never used Prefect before, let's start by exploring the core concepts:

1. [Flows & tasks](/tutorial/first-steps/) - the core elements of Prefect.
2. [Configuration](/tutorial/flow-task-config/) - enhance your flows and tasks with parameters, retries, caching, and task runners.
3. [Execution](/tutorial/execution/) - configure how your flows and tasks run.
4. [Orchestration](/tutorial/orchestration/) - the components of Prefect that enable coordination and orchestration of your flow and task runs.
5. [Deployments](/tutorial/deployments/) - enable remote flow run execution.
6. [Storage & Infrastructure](/tutorial/storage/) - specify where your flow code is stored and how to configure the execution environment.