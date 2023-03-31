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

1. [Flows & tasks](/tutorials/first-steps/) - the core elements of Prefect.
2. [Configuration](/tutorials/flow-task-config/) - enhance your flows and tasks with parameters, retries, caching, and task runners.
3. [Execution](/tutorials/execution/) - configure how your flows and tasks run.
4. [Orchestration](/tutorials/orchestration/) - the components of Prefect that enable coordination and orchestration of your flow and task runs.
5. [Deployments](/tutorials/deployments/) - enable remote flow run execution.
6. [Storage & Infrastructure](/tutorials/storage/) - specify where your flow code is stored and how to configure the execution environment.

If you have used Prefect 1 ("Prefect Core") and are familiar with Prefect workflows, we still recommend reading through these first steps, particularly [Run a flow within a flow](/tutorials/first-steps/#run-a-flow-within-a-flow). Prefect 2 flows and subflows offer significant new functionality.


