---
description: Learn the basics of creating and running Prefect flows and tasks.
tags:
    - tutorial
    - getting started
    - basics
    - tasks
    - flows
    - subflows
    - deployments
    - workers
    - work pools
search:
  boost: 2
---
# Tutorial Overview

Prefect orchestrates workflows — it simplifies the creation, scheduling, and monitoring of complex data pipelines.
You define workflows as Python code and Prefect handles the rest.

Prefect also provides error handling, retry mechanisms, and a user-friendly dashboard for monitoring.
It's the easiest way to transform any Python function into a unit of work that can be observed and orchestrated.

This tutorial provides a guided walk-through of Prefect's core concepts and instructions on how to use them.

By the end of this tutorial you will have:

1. [Created a flow](/tutorial/flows/)
2. [Added tasks to it](/tutorial/tasks/)
3. [Deployed and run the flow locally](/tutorial/deployments/)
4. [Created a work pool and run the flow remotely](/tutorial/work-pools/)

These four topics will get most users to their first production deployment.

Advanced users that need more governance and control of their workflow infrastructure can go one step further by:

5. [Using a worker-based deployment](/tutorial/workers/)

If you're looking for examples of more advanced operations (like [deploying on Kubernetes](/guides/deployment/kubernetes/)), check out Prefect's [guides](/guides/).

## Prerequisites

Before you start, make sure you have Python installed, then install Prefect: `pip install -U prefect`

See the [install guide](/getting-started/installation/) for more detailed instructions, if needed.

To go the most out of Prefect, you need connect to a forever-free [Prefect Cloud](https://app.prefect.cloud) account.
1. Create a new account or sign in at [https://app.prefect.cloud/](https://app.prefect.cloud/).
1. Use the `prefect cloud login` CLI command to [authenticate to Prefect Cloud](/cloud/users/api-keys/) from your environment.

<div class="terminal">

```bash
prefect cloud login
```

</div>

Choose **Log in with a web browser** and click the **Authorize** button in the browser window that opens.

As an alternative to using Prefect Cloud, you can self-host a [Prefect server instance](/host/).
If you choose this option, run `prefect server start` to start a local Prefect server instance.

## [First steps: Flows](/tutorial/flows/)

Let's begin by learning how to create your first Prefect flow - [click here to get started](/tutorial/flows/).
