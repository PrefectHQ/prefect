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

This tutorial provides a guided walk-through of Prefect core concepts and instructions on how to use them.

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

1. Before you start, make sure you have Python installed, then install Prefect: `pip install -U prefect`
      1. See the [install guide](/getting-started/installation/) for more detailed instructions.

2. This tutorial requires the Prefect API, so sign up for a forever free [Prefect Cloud Account](https://app.prefect.cloud/) or, alternatively, self-host a [Prefect Server](/host/).

## What is Prefect?

Prefect orchestrates workflows — it simplifies the creation, scheduling, and monitoring of complex data pipelines.
With Prefect, you define workflows as Python code and let it handle the rest.

Prefect also provides error handling, retry mechanisms, and a user-friendly dashboard for monitoring.
It's the easiest way to transform any Python function into a unit of work that can be observed and orchestrated.

Just bring your Python code, sprinkle in a few decorators, and go!

## [First steps: Flows](/tutorial/flows/)

Let's begin by learning how to create your first Prefect flow - [click here to get started](/tutorial/flows/).
